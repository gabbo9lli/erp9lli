from typing import Optional, List, Dict, Any
from datetime import date
import io
import csv
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from models import JournalEntry, JournalItem, AccountingCausal, Account, Invoice
from services.event_dispatcher import dispatch_event

class AccountingService:
    @staticmethod
    def get_next_journal_entry_number(db: Session, anno: int) -> int:
        max_num = db.query(func.max(JournalEntry.numero)).filter_by(anno=anno).scalar()
        return (max_num or 0) + 1

    @classmethod
    def create_journal_entry(cls, db: Session, data: dict) -> JournalEntry:
        causale = data.get('causale')
        items_data = data.get('items', [])
        if not causale:
            raise HTTPException(status_code=400, detail="causale is required")
        if not items_data:
            raise HTTPException(status_code=400, detail="At least one journal item is required")

        totale_dare = 0.0
        totale_avere = 0.0
        journal_items = []

        for item in items_data:
            acc_id = item.get('account_id')
            if not acc_id:
                raise HTTPException(status_code=400, detail="account_id is required for all items")
            account = db.get(Account, acc_id)
            if not account:
                raise HTTPException(status_code=404, detail=f"Conto {acc_id} non trovato")
            dare = float(item.get('dare', 0.0))
            avere = float(item.get('avere', 0.0))
            if dare == 0 and avere == 0:
                raise HTTPException(status_code=400, detail="dare e avere non possono essere entrambi zero")
            if dare > 0 and avere > 0:
                raise HTTPException(status_code=400, detail="una riga non può avere sia dare che avere > 0")

            totale_dare += dare
            totale_avere += avere

            journal_items.append(JournalItem(
                account_id=acc_id,
                partner_id=item.get('partner_id'),
                dare=round(dare, 2),
                avere=round(avere, 2),
                descrizione_riga=item.get('descrizione_riga')
            ))

        if abs(totale_dare - totale_avere) > 0.001:
            raise HTTPException(status_code=400, detail=f"Registrazione sbilanciata: Dare {totale_dare:.2f} != Avere {totale_avere:.2f}")

        reg_date_str = data.get('data_registrazione')
        reg_date = datetime.strptime(reg_date_str, '%Y-%m-%d').date() if reg_date_str else date.today()
        comp_date_str = data.get('data_competenza')
        comp_date = datetime.strptime(comp_date_str, '%Y-%m-%d').date() if comp_date_str else None
        anno = reg_date.year
        numero = cls.get_next_journal_entry_number(db, anno)
        numero_completo = f"PN-{anno}-{numero:04d}"

        entry = JournalEntry(
            numero=numero,
            anno=anno,
            numero_completo=numero_completo,
            data_registrazione=reg_date,
            data_competenza=comp_date,
            causale_id=data.get('causale_id'),
            causale=causale,
            totale_dare=totale_dare,
            totale_avere=totale_avere,
            stato=data.get('stato', 'confermata'),
            note=data.get('note'),
            items=journal_items
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @classmethod
    def auto_post_invoice_to_accounting(cls, db: Session, invoice: Invoice) -> Optional[JournalEntry]:
        from seed_accounting import seed_default_accounting_causals
        seed_default_accounting_causals(db)

        causal = db.query(AccountingCausal).filter_by(codice="FATTURA_VENDITA", attivo=True).first()
        if not causal or not causal.conto_dare_id or not causal.conto_avere_id or not causal.conto_iva_id:
            return None

        anno = invoice.data_documento.year
        num = cls.get_next_journal_entry_number(db, anno)
        numero_completo = f"PN-{anno}-{num:04d}"
        tot_fatt = float(invoice.totale_fattura)
        tot_imp = float(invoice.totale_imponibile)
        tot_iva = float(invoice.totale_imposta)

        je = JournalEntry(
            numero=num,
            anno=anno,
            numero_completo=numero_completo,
            data_registrazione=date.today(),
            data_competenza=invoice.data_documento,
            causale=f"Emissione Fattura {invoice.numero_completo}",
            causale_id=causal.id,
            totale_dare=tot_fatt,
            totale_avere=tot_fatt,
            stato="confermata"
        )
        db.add(je)
        db.flush()

        db.add(JournalItem(
            journal_entry_id=je.id,
            account_id=causal.conto_dare_id,
            partner_id=invoice.cliente_id,
            descrizione_riga=f"Credito v/cliente {invoice.numero_completo}",
            dare=tot_fatt,
            avere=0.0
        ))
        db.add(JournalItem(
            journal_entry_id=je.id,
            account_id=causal.conto_avere_id,
            descrizione_riga=f"Ricavo vendita {invoice.numero_completo}",
            dare=0.0,
            avere=tot_imp
        ))
        db.add(JournalItem(
            journal_entry_id=je.id,
            account_id=causal.conto_iva_id,
            descrizione_riga=f"IVA a debito {invoice.numero_completo}",
            dare=0.0,
            avere=tot_iva
        ))
        return je
