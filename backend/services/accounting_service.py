from typing import Optional, List, Dict, Any
from datetime import datetime, date
import io
import csv
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from models import JournalEntry, JournalItem, AccountingCausal, Account, Invoice, InvoiceInstallment
from seed_accounting import seed_default_accounting_causals

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
            totale_dare=round(totale_dare, 2),
            totale_avere=round(totale_avere, 2),
            stato=data.get('stato', 'confermata'),
            note=data.get('note'),
            items=journal_items
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @classmethod
    def auto_post_invoice_to_accounting(cls, db: Session, inv: Invoice) -> Optional[JournalEntry]:
        seed_default_accounting_causals(db)
        causal = db.query(AccountingCausal).filter_by(codice="VEND_FATT", attivo=True).first()
        if not causal or not (causal.conto_dare_id and causal.conto_avere_id and causal.conto_iva_id):
            return None

        anno = inv.anno or (inv.data_documento.year if inv.data_documento else date.today().year)
        num = cls.get_next_journal_entry_number(db, anno)
        num_comp = f"PN-{anno}-{num:04d}"
        tot_lordo = float(inv.totale_fattura)
        tot_iva = float(inv.totale_imposta or 0.0)
        tot_imp = round(tot_lordo - tot_iva, 2)

        cli_nome = inv.cliente.ragione_sociale if inv.cliente else "Cliente"
        desc_entry = f"Fattura {inv.numero_completo} a {cli_nome}"

        je = JournalEntry(
            numero=num,
            anno=anno,
            numero_completo=num_comp,
            data_registrazione=inv.data_documento or date.today(),
            data_competenza=inv.data_documento or date.today(),
            causale=desc_entry,
            causale_id=causal.id,
            totale_dare=tot_lordo,
            totale_avere=tot_lordo,
            stato="confermata"
        )
        db.add(je)
        db.flush()

        db.add(JournalItem(
            journal_entry_id=je.id,
            account_id=causal.conto_dare_id,
            partner_id=inv.cliente_id,
            descrizione_riga=f"Credito fattura {inv.numero_completo}",
            dare=tot_lordo,
            avere=0.0
        ))
        db.add(JournalItem(
            journal_entry_id=je.id,
            account_id=causal.conto_avere_id,
            descrizione_riga=f"Ricavo vendita {inv.numero_completo}",
            dare=0.0,
            avere=tot_imp
        ))
        if tot_iva > 0:
            db.add(JournalItem(
                journal_entry_id=je.id,
                account_id=causal.conto_iva_id,
                descrizione_riga=f"IVA a debito {inv.numero_completo}",
                dare=0.0,
                avere=tot_iva
            ))
        return je

    @classmethod
    def auto_post_credit_note_to_accounting(cls, db: Session, nc: Invoice, inv: Invoice) -> Optional[JournalEntry]:
        seed_default_accounting_causals(db)
        causal_nc = db.query(AccountingCausal).filter_by(codice="VEND_NC", attivo=True).first()
        if not (causal_nc and causal_nc.conto_dare_id and causal_nc.conto_avere_id and causal_nc.conto_iva_id):
            return None

        anno_c = date.today().year
        num_c = cls.get_next_journal_entry_number(db, anno_c)
        num_comp_c = f"PN-{anno_c}-{num_c:04d}"
        tot_lordo_c = float(nc.totale_fattura)
        tot_iva_c = float(nc.totale_imposta or 0.0)
        tot_imp_c = round(tot_lordo_c - tot_iva_c, 2)
        cli_nome = inv.cliente.ragione_sociale if inv.cliente else "Cliente"

        je_nc = JournalEntry(
            numero=num_c,
            anno=anno_c,
            numero_completo=num_comp_c,
            data_registrazione=date.today(),
            data_competenza=date.today(),
            causale=f"Nota di Credito {nc.numero_completo} su {inv.numero_completo} a {cli_nome}",
            causale_id=causal_nc.id,
            totale_dare=tot_lordo_c,
            totale_avere=tot_lordo_c,
            stato="confermata"
        )
        db.add(je_nc)
        db.flush()

        db.add(JournalItem(
            journal_entry_id=je_nc.id,
            account_id=causal_nc.conto_dare_id,
            descrizione_riga=f"Storno ricavi {nc.numero_completo}",
            dare=tot_imp_c,
            avere=0.0
        ))
        db.add(JournalItem(
            journal_entry_id=je_nc.id,
            account_id=causal_nc.conto_iva_id,
            descrizione_riga=f"Storno IVA a debito {nc.numero_completo}",
            dare=tot_iva_c,
            avere=0.0
        ))
        db.add(JournalItem(
            journal_entry_id=je_nc.id,
            account_id=causal_nc.conto_avere_id,
            partner_id=nc.cliente_id,
            descrizione_riga=f"Storno credito cliente {nc.numero_completo}",
            dare=0.0,
            avere=tot_lordo_c
        ))
        return je_nc

    @classmethod
    def auto_post_installment_payment_to_accounting(cls, db: Session, inst: InvoiceInstallment, invoice: Invoice) -> Optional[JournalEntry]:
        seed_default_accounting_causals(db)
        causal_inc = db.query(AccountingCausal).filter_by(codice="INCASSO_RATA", attivo=True).first()
        if not (causal_inc and causal_inc.conto_dare_id and causal_inc.conto_avere_id):
            return None

        anno_c = date.today().year
        num_c = cls.get_next_journal_entry_number(db, anno_c)
        num_comp_c = f"PN-{anno_c}-{num_c:04d}"
        importo_inc = float(inst.importo)
        cli_nome = invoice.cliente.ragione_sociale if invoice.cliente else "Cliente"

        je_inc = JournalEntry(
            numero=num_c,
            anno=anno_c,
            numero_completo=num_comp_c,
            data_registrazione=date.today(),
            data_competenza=date.today(),
            causale=f"Incasso rata {inst.numero_rata}/{inst.totale_rate} fattura {invoice.numero_completo} da {cli_nome}",
            causale_id=causal_inc.id,
            totale_dare=importo_inc,
            totale_avere=importo_inc,
            stato="confermata"
        )
        db.add(je_inc)
        db.flush()

        db.add(JournalItem(
            journal_entry_id=je_inc.id,
            account_id=causal_inc.conto_dare_id,
            descrizione_riga=f"Incasso banca rata {inst.numero_rata} FT {invoice.numero_completo}",
            dare=importo_inc,
            avere=0.0
        ))
        db.add(JournalItem(
            journal_entry_id=je_inc.id,
            account_id=causal_inc.conto_avere_id,
            partner_id=invoice.cliente_id,
            descrizione_riga=f"Chiusura credito rata {inst.numero_rata} FT {invoice.numero_completo}",
            dare=0.0,
            avere=importo_inc
        ))
        return je_inc
