from datetime import datetime, date
from sqlalchemy import func
from models import db, Partner, Product, CustomerOrder, OrderItem, EcommerceSyncLog, PurchaseDeliveryNoteItem, DeliveryNoteItem, PosSaleItem
from services.event_dispatcher import dispatch_event

class EcommerceService:
    @staticmethod
    def process_incoming_order(payload: dict) -> tuple[CustomerOrder, bool]:
        ext_ref = (payload.get('number') or payload.get('id') or '').strip()
        if not ext_ref:
            ext_ref = f"WEB-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        # 1. Idempotency check: if order with this external_reference already exists, return it!
        existing = CustomerOrder.query.filter_by(external_reference=ext_ref).first()
        if existing:
            log = EcommerceSyncLog(
                tipo_operazione="import_order",
                external_order_id=ext_ref,
                customer_order_id=existing.id,
                stato="success",
                payload_ricevuto=payload,
                dettaglio_risposta="Ordine già presente a sistema (risposta idempotente)."
            )
            db.session.add(log)
            db.session.commit()
            return existing, False

        # 2. Customer Lookup or Auto-provisioning
        email = (payload.get('email') or '').strip().lower()
        bill_addr = payload.get('bill_address') or {}
        first_name = bill_addr.get('firstname') or ''
        last_name = bill_addr.get('lastname') or ''
        full_name = f"{first_name} {last_name}".strip()
        if not full_name:
            full_name = payload.get('customer_name') or email or 'Cliente E-Commerce'

        partner = None
        if email:
            partner = Partner.query.filter(func.lower(Partner.pec) == email).first()
        if not partner:
            partner = Partner.query.filter(func.lower(Partner.ragione_sociale) == full_name.lower()).first()

        if not partner:
            partner = Partner(
                ragione_sociale=full_name,
                tipo='cliente',
                pec=email,
                indirizzo=bill_addr.get('address1') or bill_addr.get('address'),
                cap=bill_addr.get('zipcode'),
                citta=bill_addr.get('city'),
                nazione=bill_addr.get('country') or 'IT'
            )
            db.session.add(partner)
            db.session.flush()

        # 3. Order Numbering
        year = datetime.utcnow().year
        prefix = f"ORD-{year}-"
        max_num = db.session.query(func.max(CustomerOrder.numero)).filter_by(anno=year).scalar()
        next_num = (max_num or 0) + 1
        num_comp = f"{prefix}{next_num:04d}"

        order = CustomerOrder(
            numero=next_num,
            anno=year,
            numero_completo=num_comp,
            data_ordine=date.today(),
            data_richiesta=date.today(),
            cliente_id=partner.id,
            stato="confermato",
            external_reference=ext_ref,
            canale_vendita="ecommerce",
            note=f"Ordine importato da Spree Commerce #{ext_ref}"
        )
        db.session.add(order)
        db.session.flush()

        # 4. Line items with step 5 sequences (5, 10, 15...)
        line_items = payload.get('line_items') or payload.get('items') or []
        tot_imponibile = 0.0
        seq = 5

        for item_data in line_items:
            sku = (item_data.get('sku') or item_data.get('product_code') or '').strip()
            prod = Product.query.filter_by(codice=sku).first() if sku else None
            if not prod and item_data.get('product_id'):
                prod = db.session.get(Product, item_data['product_id'])

            if not prod:
                desc = item_data.get('name') or sku or 'Articolo Web'
                prod = Product(codice=sku or f"WEB-{seq}", descrizione=desc, prezzo_vendita=float(item_data.get('price', 0.0)))
                db.session.add(prod)
                db.session.flush()

            qty = float(item_data.get('quantity') or item_data.get('quantita') or 1.0)
            price = float(item_data.get('price') or item_data.get('prezzo_unitario') or prod.prezzo_vendita or 0.0)
            subtot = round(qty * price, 2)
            tot_imponibile += subtot

            order_item = OrderItem(
                order_id=order.id,
                sequenza=seq,
                product_id=prod.id,
                descrizione=prod.descrizione or 'Articolo Bio',
                unita_misura=prod.unita_misura or 'KG',
                quantita_ordinata=qty,
                quantita_consegnata=0.0,
                colli_ordinati=int(item_data.get('colli', 1)),
                colli_consegnati=0,
                prezzo_unitario=price,
                aliquota_iva=int(prod.aliquota_iva or 4),
                stato='aperto'
            )
            db.session.add(order_item)
            seq += 5

        order.totale_imponibile = round(tot_imponibile, 2)

        # 5. Log sync
        log = EcommerceSyncLog(
            tipo_operazione="import_order",
            external_order_id=ext_ref,
            customer_order_id=order.id,
            stato="success",
            payload_ricevuto=payload,
            dettaglio_risposta=f"Creato ordine {order.numero_completo} con {len(line_items)} righe."
        )
        db.session.add(log)
        db.session.commit()

        # 6. Event Bus
        try:
            dispatch_event(
                azione="ordine_ecommerce_ricevuto",
                titolo=f"Ordine E-Commerce {ext_ref}",
                descrizione=f"Importato ordine web #{ext_ref} in {order.numero_completo} ({partner.ragione_sociale})",
                channel_code="WEBHOOK",
                category_code="VENDITE",
                entita_tipo="customer_order",
                entita_id=order.id,
                partner_id=partner.id,
                payload_dati={"external_reference": ext_ref, "totale": float(order.totale_imponibile)}
            )
        except Exception:
            pass

        return order, True

    @staticmethod
    def get_stock_sync_feed() -> list[dict]:
        products = Product.query.filter_by(attivo=True).all()
        feed = []

        for p in products:
            carichi = db.session.query(func.coalesce(func.sum(PurchaseDeliveryNoteItem.quantita), 0.0)).filter_by(product_id=p.id).scalar() or 0.0
            scarichi_ddt = db.session.query(func.coalesce(func.sum(DeliveryNoteItem.quantita), 0.0)).filter_by(product_id=p.id).scalar() or 0.0
            scarichi_pos = db.session.query(func.coalesce(func.sum(PosSaleItem.quantita), 0.0)).filter_by(product_id=p.id).scalar() or 0.0

            giacenza = max(0.0, round(float(carichi) - float(scarichi_ddt) - float(scarichi_pos), 2))
            feed.append({
                "id": p.id,
                "sku": p.codice,
                "name": p.descrizione,
                "price": float(p.prezzo_vendita or 0.0),
                "stock": giacenza,
                "in_stock": giacenza > 0,
                "unita_misura": p.unita_misura or "KG"
            })

        return feed
