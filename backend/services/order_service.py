from typing import Optional, List, Dict, Any
from datetime import datetime, date
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from models import CustomerOrder, OrderItem, DeliveryNote, DeliveryNoteItem, Partner, Product
from services.event_dispatcher import dispatch_event

class OrderService:
    @staticmethod
    def get_next_order_number(db: Session, anno: int) -> int:
        max_num = db.query(func.max(CustomerOrder.numero)).filter_by(anno=anno).scalar()
        return (max_num or 0) + 1

    @staticmethod
    def get_next_ddt_number(db: Session, anno: int) -> int:
        max_num = db.query(func.max(DeliveryNote.numero)).filter_by(anno=anno).scalar()
        return (max_num or 0) + 1

    @classmethod
    def create_order(cls, db: Session, data: dict) -> CustomerOrder:
        cliente_id = data.get('cliente_id')
        if not cliente_id:
            raise HTTPException(status_code=400, detail="cliente_id is required")
        cliente = db.get(Partner, cliente_id)
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente not found")

        items_data = data.get('items', [])
        if not items_data:
            raise HTTPException(status_code=400, detail="At least one item is required")

        doc_date_str = data.get('data_ordine')
        doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()
        req_date_str = data.get('data_richiesta')
        req_date = datetime.strptime(req_date_str, '%Y-%m-%d').date() if req_date_str else None
        conf_date_str = data.get('data_confermata')
        conf_date = datetime.strptime(conf_date_str, '%Y-%m-%d').date() if conf_date_str else None

        anno = doc_date.year
        numero = cls.get_next_order_number(db, anno)
        numero_completo = f"ORD-{anno}-{numero:04d}"

        totale_imponibile = 0.0
        order_items = []
        seq = 5

        for it in items_data:
            prod_id = it.get('product_id')
            product = db.get(Product, prod_id) if prod_id else None
            descrizione = it.get('descrizione', product.descrizione if product else 'Articolo')
            unita_misura = it.get('unita_misura', product.unita_misura if product else 'KG')
            colli = int(it.get('colli_ordinati', 1))
            qta = float(it.get('quantita_ordinata', 1.0))
            prezzo = float(it.get('prezzo_unitario', product.prezzo_vendita if product else 0.0))
            aliquota = int(it.get('aliquota_iva', product.aliquota_iva if product else 4))
            lotto = it.get('lotto')

            totale_imponibile += round(qta * prezzo, 2)

            riga_seq = int(it.get('sequenza', seq))
            seq = max(seq, riga_seq) + 5

            order_items.append(OrderItem(
                product_id=prod_id,
                sequenza=riga_seq,
                descrizione=descrizione,
                unita_misura=unita_misura,
                colli_ordinati=colli,
                quantita_ordinata=qta,
                colli_consegnati=0,
                quantita_consegnata=0.0,
                prezzo_unitario=prezzo,
                aliquota_iva=aliquota,
                lotto=lotto,
                stato='aperto'
            ))

        order = CustomerOrder(
            numero=numero,
            anno=anno,
            numero_completo=numero_completo,
            data_ordine=doc_date,
            data_richiesta=req_date,
            data_confermata=conf_date,
            cliente_id=cliente.id,
            stato='aperto',
            totale_imponibile=round(totale_imponibile, 2),
            note=data.get('note'),
            items=order_items
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def update_order(db: Session, oid: int, data: dict) -> CustomerOrder:
        order = db.get(CustomerOrder, oid)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.stato == 'chiuso':
            raise HTTPException(status_code=400, detail="Impossibile modificare un ordine chiuso")

        if 'note' in data:
            order.note = data['note']
        if 'data_richiesta' in data:
            order.data_richiesta = datetime.strptime(data['data_richiesta'], '%Y-%m-%d').date() if data['data_richiesta'] else None
        if 'data_confermata' in data:
            order.data_confermata = datetime.strptime(data['data_confermata'], '%Y-%m-%d').date() if data['data_confermata'] else None

        db.commit()
        db.refresh(order)
        return order

    @classmethod
    def fulfill_to_ddt(cls, db: Session, oid: int, data: dict) -> tuple[DeliveryNote, CustomerOrder]:
        order = db.get(CustomerOrder, oid)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.stato == 'chiuso':
            raise HTTPException(status_code=400, detail="L'ordine è già interamente chiuso")

        items_to_fulfill = data.get('items', [])
        if not items_to_fulfill:
            items_to_fulfill = [
                {"order_item_id": it.id, "colli": it.colli_residui, "quantita": it.quantita_residua}
                for it in order.items if it.quantita_residua > 0
            ]

        ddt_date = date.today()
        ddt_anno = ddt_date.year
        ddt_num = cls.get_next_ddt_number(db, ddt_anno)
        ddt_numero_completo = f"DDT-{ddt_anno}-{ddt_num:04d}"

        ddt_items = []
        totale_imponibile_ddt = 0.0
        colli_totali_ddt = 0
        peso_totale_netto_ddt = 0.0

        items_dict = {it.id: it for it in order.items}

        for fulfill_req in items_to_fulfill:
            it_id = fulfill_req.get('order_item_id')
            order_item = items_dict.get(it_id)
            if not order_item:
                continue

            qta_evasa = float(fulfill_req.get('quantita', order_item.quantita_residua))
            colli_evasi = int(fulfill_req.get('colli', order_item.colli_residui))
            if qta_evasa <= 0:
                continue

            order_item.quantita_consegnata = round(order_item.quantita_consegnata + qta_evasa, 2)
            order_item.colli_consegnati += colli_evasi

            if order_item.quantita_consegnata >= order_item.quantita_ordinata:
                order_item.stato = 'chiuso'

            imp_riga = round(qta_evasa * order_item.prezzo_unitario, 2)
            totale_imponibile_ddt += imp_riga
            colli_totali_ddt += colli_evasi
            peso_totale_netto_ddt += qta_evasa

            ddt_item = DeliveryNoteItem(
                product_id=order_item.product_id,
                descrizione=order_item.descrizione,
                unita_misura=order_item.unita_misura,
                colli=colli_evasi,
                quantita=qta_evasa,
                prezzo_unitario=order_item.prezzo_unitario,
                aliquota_iva=order_item.aliquota_iva,
                lotto=fulfill_req.get('lotto', order_item.lotto)
            )
            ddt_items.append(ddt_item)

        if not ddt_items:
            raise HTTPException(status_code=400, detail="Nessuna quantità valida da evadere")

        ddt = DeliveryNote(
            numero=ddt_num,
            anno=ddt_anno,
            numero_completo=ddt_numero_completo,
            data_documento=ddt_date,
            cliente_id=order.cliente_id,
            causale_trasporto='Vendita',
            porto='Franco',
            aspetto_beni='Colli',
            colli_totali=colli_totali_ddt,
            peso_totale_netto=round(peso_totale_netto_ddt, 2),
            peso_totale_lordo=round(peso_totale_netto_ddt * 1.05, 2),
            totale_imponibile=round(totale_imponibile_ddt, 2),
            stato='confermato',
            note=f"Evasione da Ordine {order.numero_completo}",
            items=ddt_items
        )
        db.add(ddt)

        if all(it.stato == 'chiuso' for it in order.items):
            order.stato = 'chiuso'
        else:
            order.stato = 'in_lavorazione'

        db.commit()
        db.refresh(order)
        db.refresh(ddt)
        return ddt, order
