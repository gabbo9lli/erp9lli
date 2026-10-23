from typing import Optional, List, Dict, Any
from datetime import datetime, date
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from models import DeliveryNote, DeliveryNoteItem, Partner, Product
from services.event_dispatcher import dispatch_event

class DeliveryNoteService:
    @staticmethod
    def get_next_ddt_number(db: Session, anno: int) -> int:
        max_num = db.query(func.max(DeliveryNote.numero)).filter_by(anno=anno).scalar()
        return (max_num or 0) + 1

    @classmethod
    def create_delivery_note(cls, db: Session, data: dict) -> DeliveryNote:
        cliente_id = data.get('cliente_id')
        if not cliente_id:
            raise HTTPException(status_code=400, detail="cliente_id is required")

        cliente = db.get(Partner, cliente_id)
        if not cliente:
            raise HTTPException(status_code=400, detail="Cliente partner not found")

        items_data = data.get('items', [])
        if not items_data:
            raise HTTPException(status_code=400, detail="At least one item is required in delivery note")

        doc_date_str = data.get('data_documento')
        doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()

        anno = doc_date.year
        numero = cls.get_next_ddt_number(db, anno)
        numero_completo = f"DDT-{anno}-{numero:04d}"

        colli_totali = 0
        peso_totale_netto = 0.0
        peso_totale_lordo = 0.0
        totale_imponibile = 0.0

        ddt_items = []
        for idx, item in enumerate(items_data):
            prod_id = item.get('product_id')
            if not prod_id:
                raise HTTPException(status_code=400, detail=f"Item {idx+1}: product_id is required")
            product = db.get(Product, prod_id)
            if not product:
                raise HTTPException(status_code=400, detail=f"Item {idx+1}: product not found")

            colli = int(item.get('colli', 1))
            quantita = float(item.get('quantita', 1.0))
            prezzo_unitario = float(item.get('prezzo_unitario', product.prezzo_vendita))
            aliquota_iva = int(item.get('aliquota_iva', product.aliquota_iva))
            descrizione = item.get('descrizione', product.descrizione)
            unita_misura = item.get('unita_misura', product.unita_misura)
            lotto = item.get('lotto')
            data_scadenza_str = item.get('data_scadenza')

            # Controllo tracciabilità biologica (ReteBio standard)
            if product.in_scadenza:
                if not lotto or not data_scadenza_str:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Prodotto biologico in scadenza '{product.descrizione}': lotto e data di scadenza sono obbligatori!"
                    )

            data_scadenza = datetime.strptime(data_scadenza_str, '%Y-%m-%d').date() if data_scadenza_str else None

            colli_totali += colli
            if unita_misura.upper() == 'KG':
                peso_netto_riga = quantita
            else:
                peso_netto_riga = quantita * (product.peso_netto or 1.0)
            peso_totale_netto += peso_netto_riga
            peso_totale_lordo += peso_netto_riga + (colli * (product.tara or 0.0))
            totale_imponibile += (quantita * prezzo_unitario)

            ddt_item = DeliveryNoteItem(
                product_id=product.id,
                descrizione=descrizione,
                unita_misura=unita_misura,
                colli=colli,
                quantita=quantita,
                prezzo_unitario=prezzo_unitario,
                aliquota_iva=aliquota_iva,
                lotto=lotto,
                data_scadenza=data_scadenza
            )
            ddt_items.append(ddt_item)

        ddt = DeliveryNote(
            numero=numero,
            anno=anno,
            numero_completo=numero_completo,
            data_documento=doc_date,
            cliente_id=cliente.id,
            vettore_id=data.get('vettore_id'),
            causale_trasporto=data.get('causale_trasporto', 'Vendita'),
            porto=data.get('porto', 'Franco'),
            aspetto_beni=data.get('aspetto_beni', 'Colli'),
            colli_totali=colli_totali,
            peso_totale_netto=round(peso_totale_netto, 2),
            peso_totale_lordo=round(peso_totale_lordo, 2),
            totale_imponibile=round(totale_imponibile, 2),
            stato='bozza',
            note=data.get('note'),
            items=ddt_items
        )
        db.add(ddt)
        db.commit()
        db.refresh(ddt)
        return ddt

    @staticmethod
    def update_delivery_note(db: Session, did: int, data: dict) -> DeliveryNote:
        ddt = db.get(DeliveryNote, did)
        if not ddt:
            raise HTTPException(status_code=404, detail="Delivery note not found")
        if ddt.stato != 'bozza':
            raise HTTPException(status_code=400, detail=f"Impossibile modificare un DDT in stato '{ddt.stato}' (confermato)")

        for key in ('vettore_id', 'causale_trasporto', 'porto', 'aspetto_beni', 'note'):
            if key in data:
                setattr(ddt, key, data[key])

        db.commit()
        db.refresh(ddt)
        return ddt

    @staticmethod
    def delete_delivery_note(db: Session, did: int) -> None:
        ddt = db.get(DeliveryNote, did)
        if not ddt:
            raise HTTPException(status_code=404, detail="Delivery note not found")
        if ddt.stato != 'bozza':
            raise HTTPException(status_code=400, detail=f"Impossibile eliminare un DDT in stato '{ddt.stato}' (confermato)")

        db.delete(ddt)
        db.commit()

    @staticmethod
    def confirm_delivery_note(db: Session, did: int) -> DeliveryNote:
        ddt = db.get(DeliveryNote, did)
        if not ddt:
            raise HTTPException(status_code=404, detail="Delivery note not found")
        if not ddt.items:
            raise HTTPException(status_code=400, detail="Impossibile confermare un DDT senza righe merce")

        ddt.stato = 'confermato'
        db.commit()
        db.refresh(ddt)

        try:
            dispatch_event(
                db=db,
                azione="emissione_ddt",
                titolo=f"Emissione DDT {ddt.numero_completo}",
                descrizione=f"DDT emesso per cliente {ddt.cliente.ragione_sociale}",
                channel_code="AUDIT",
                category_code="LOGISTICA",
                entita_tipo="delivery_note",
                entita_id=ddt.id,
                partner_id=ddt.cliente_id
            )
        except Exception:
            pass

        return ddt
