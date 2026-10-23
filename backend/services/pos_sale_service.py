from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from models import (
    PosStation, PosSale, PosSaleItem, Product, User,
    JournalEntry, JournalItem, AccountingCausal, Account,
    PurchaseDeliveryNoteItem
)
from services.pos_driver_service import PosDriverService
from services.event_dispatcher import dispatch_event
from services.accounting_service import AccountingService
from seed_accounting import seed_default_accounting_causals

DEFAULT_POS_STATIONS = [
    {
        "codice": "CASSA_01",
        "nome": "Cassa Banco Principale",
        "driver_tipo": "simulator",
        "matricola_rt": "99MEY123456",
        "intestazione": "ReteBio Società Cooperativa Agricola\nVia della Spiga 12, Bologna (BO)",
        "pie_pagina": "Grazie per aver scelto il biologico!"
    }
]

class PosSaleService:
    @staticmethod
    def seed_default_pos_stations(db: Session):
        for st_data in DEFAULT_POS_STATIONS:
            if not db.query(PosStation).filter_by(codice=st_data["codice"]).first():
                db.add(PosStation(**st_data))
        db.commit()

    @staticmethod
    def get_next_pos_sale_number(db: Session, anno: int) -> str:
        max_num = db.query(func.max(PosSale.id)).scalar() or 0
        next_num = max_num + 1
        return f"SC-{anno}-{next_num:04d}"

    @classmethod
    def create_pos_sale(cls, db: Session, data: dict, current_user: Optional[User] = None) -> Tuple[PosSale, dict]:
        cls.seed_default_pos_stations(db)
        station_id = data.get('pos_station_id')
        if not station_id:
            st = db.query(PosStation).filter_by(attivo=True).first()
            station_id = st.id if st else None

        station = db.get(PosStation, station_id) if station_id else None
        if not station:
            raise HTTPException(status_code=400, detail="Punto Cassa non valido o non configurato")

        items_data = data.get('items', [])
        if not items_data:
            raise HTTPException(status_code=400, detail="Il carrello della vendita è vuoto")

        totale_lordo = 0.0
        totale_imponibile = 0.0
        totale_iva = 0.0
        sale_items = []

        for it in items_data:
            p_id = it.get('product_id')
            prod = db.get(Product, p_id)
            if not prod:
                raise HTTPException(status_code=404, detail=f"Prodotto ID {p_id} non trovato")

            qty = float(it.get('quantita', 1.0))
            price = float(it.get('prezzo_unitario', prod.prezzo_vendita or 0.0))
            subtot = round(qty * price, 2)
            aliquota = float(prod.aliquota_iva or 22.0)
            imp = round(subtot / (1.0 + aliquota / 100.0), 2)
            iva = round(subtot - imp, 2)

            lotto = it.get('lotto')
            scadenza = None
            if it.get('data_scadenza'):
                try:
                    scadenza = datetime.strptime(it['data_scadenza'][:10], '%Y-%m-%d').date()
                except Exception:
                    pass

            if prod.in_scadenza and not lotto:
                carichi = db.query(
                    PurchaseDeliveryNoteItem.lotto,
                    PurchaseDeliveryNoteItem.data_scadenza,
                    func.sum(PurchaseDeliveryNoteItem.quantita).label('carico')
                ).filter_by(product_id=prod.id).group_by(
                    PurchaseDeliveryNoteItem.lotto,
                    PurchaseDeliveryNoteItem.data_scadenza
                ).order_by(PurchaseDeliveryNoteItem.data_scadenza.asc()).all()

                if carichi:
                    lotto = carichi[0].lotto
                    scadenza = carichi[0].data_scadenza

            totale_lordo += subtot
            totale_imponibile += imp
            totale_iva += iva

            sale_item = PosSaleItem(
                product_id=prod.id,
                quantita=qty,
                prezzo_unitario=price,
                aliquota_iva=aliquota,
                subtotale=subtot,
                lotto=lotto,
                data_scadenza=scadenza
            )
            sale_items.append(sale_item)

        totale_lordo = round(totale_lordo, 2)
        totale_iva = round(totale_iva, 2)
        totale_imponibile = round(totale_lordo - totale_iva, 2)

        metodo_pagamento = (data.get('metodo_pagamento') or 'contanti').lower()
        importo_pagato = float(data.get('importo_pagato', totale_lordo))

        if metodo_pagamento == 'contanti' and importo_pagato < (totale_lordo - 0.001):
            raise HTTPException(
                status_code=400,
                detail=f"Importo pagato ({importo_pagato:.2f} €) insufficiente per il totale di {totale_lordo:.2f} €"
            )

        importo_resto = max(0.0, round(importo_pagato - totale_lordo, 2)) if metodo_pagamento == 'contanti' else 0.0

        year = datetime.utcnow().year
        numero_scontrino = cls.get_next_pos_sale_number(db, year)

        email = getattr(current_user, 'email', 'cassa@retebio.it') if current_user else 'cassa@retebio.it'

        sale = PosSale(
            pos_station_id=station.id,
            numero_scontrino=numero_scontrino,
            data_ora=datetime.utcnow(),
            totale_lordo=totale_lordo,
            totale_imponibile=totale_imponibile,
            totale_iva=totale_iva,
            metodo_pagamento=metodo_pagamento,
            importo_pagato=importo_pagato,
            importo_resto=importo_resto,
            stato='emesso',
            utente_id=current_user.id if current_user else None,
            utente_email=email,
            cliente_id=data.get('cliente_id')
        )
        for si in sale_items:
            sale.items.append(si)

        db.add(sale)
        db.flush()

        ticket_res = PosDriverService.print_ticket(sale, station)
        sale.stato_fiscale_rt = ticket_res.get('stato_fiscale', 'simulato')
        sale.dettaglio_rt_risposta = ticket_res.get('messaggio')

        # Registrazione automatica Partita Doppia
        seed_default_accounting_causals(db)
        causal_pos = db.query(AccountingCausal).filter_by(codice="CORRISPETTIVO", attivo=True).first()

        acc_cassa = causal_pos.conto_dare if (causal_pos and causal_pos.conto_dare) else db.query(Account).filter(Account.codice.in_(["1001", "1.01.01.01"])).first()
        acc_pos = db.query(Account).filter(Account.codice.in_(["1002", "1.01.02.01"])).first()
        acc_ricavo = causal_pos.conto_avere if (causal_pos and causal_pos.conto_avere) else db.query(Account).filter(Account.codice.in_(["4101", "4.01.01.01"])).first()
        acc_iva = causal_pos.conto_iva if (causal_pos and causal_pos.conto_iva) else db.query(Account).filter(Account.codice.in_(["2201", "2.02.01.01"])).first()

        acc_dare = acc_pos if metodo_pagamento in ['pos_carta', 'pos', 'carta'] and acc_pos else acc_cassa

        if acc_dare and acc_ricavo and acc_iva:
            anno_cont = date.today().year
            num_cont = AccountingService.get_next_journal_entry_number(db, anno_cont)
            num_comp = f"PN-{anno_cont}-{num_cont:04d}"
            je = JournalEntry(
                numero=num_cont,
                anno=anno_cont,
                numero_completo=num_comp,
                data_registrazione=date.today(),
                data_competenza=date.today(),
                causale=f"Corrispettivo di Cassa {numero_scontrino}",
                causale_id=causal_pos.id if causal_pos else None,
                totale_dare=totale_lordo,
                totale_avere=totale_lordo,
                stato="confermata"
            )
            db.add(je)
            db.flush()

            db.add(JournalItem(
                journal_entry_id=je.id,
                account_id=acc_dare.id,
                descrizione_riga=f"Incasso scontrino {numero_scontrino}",
                dare=totale_lordo,
                avere=0.0
            ))
            db.add(JournalItem(
                journal_entry_id=je.id,
                account_id=acc_ricavo.id,
                descrizione_riga=f"Corrispettivo imponibile {numero_scontrino}",
                dare=0.0,
                avere=totale_imponibile
            ))
            db.add(JournalItem(
                journal_entry_id=je.id,
                account_id=acc_iva.id,
                descrizione_riga=f"IVA vendite al banco {numero_scontrino}",
                dare=0.0,
                avere=totale_iva
            ))
            sale.journal_entry_id = je.id

        db.commit()

        try:
            dispatch_event(
                azione="vendita_banco",
                titolo=f"Scontrino Banco {numero_scontrino}",
                descrizione=f"Emesso scontrino {numero_scontrino} - Totale {totale_lordo:.2f} € ({metodo_pagamento})",
                channel_code="AUDIT",
                category_code="VENDITE",
                entita_tipo="pos_sale",
                entita_id=sale.id,
                utente_email=email,
                db=db
            )
        except Exception:
            pass

        return sale, ticket_res

    @classmethod
    def print_pos_sale(cls, db: Session, sid: int) -> dict:
        sale = db.get(PosSale, sid)
        if not sale:
            raise HTTPException(status_code=404, detail="Scontrino non trovato")
        station = sale.station or db.query(PosStation).first()
        ticket_res = PosDriverService.print_ticket(sale, station)
        return {
            "success": ticket_res.get("success", True),
            "stato_fiscale": ticket_res.get("stato_fiscale"),
            "ticket_ascii": ticket_res.get("ticket_ascii")
        }
