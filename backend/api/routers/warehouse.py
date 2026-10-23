from typing import Optional, List
from datetime import datetime, date
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import PurchaseDeliveryNote, PurchaseDeliveryNoteItem, DeliveryNoteItem, PosSaleItem, Partner, Product, User
from api.deps import require_auth
from services.barcode_label_service import BarcodeLabelService
from services.event_dispatcher import dispatch_event

router = APIRouter(prefix="/api", tags=["Warehouse & Purchases"])

@router.get("/purchases")
def get_purchases(
    fornitore_id: Optional[int] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    query = db.query(PurchaseDeliveryNote)
    if fornitore_id:
        query = query.filter_by(fornitore_id=fornitore_id)
    purchases = query.order_by(PurchaseDeliveryNote.data_ricezione.desc(), PurchaseDeliveryNote.id.desc()).all()
    return [p.to_dict() for p in purchases]

@router.get("/purchases/{pid}")
def get_purchase_detail(
    pid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    purchase = db.get(PurchaseDeliveryNote, pid)
    if not purchase:
        return JSONResponse(status_code=404, content={"error": "Purchase delivery note not found"})
    return purchase.to_dict()

@router.post("/purchases", status_code=status.HTTP_201_CREATED)
async def create_purchase(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    fornitore_id = data.get('fornitore_id')
    num_doc = data.get('numero_documento_fornitore')
    if not fornitore_id or not num_doc:
        return JSONResponse(status_code=400, content={"error": "fornitore_id e numero_documento_fornitore sono obbligatori"})

    supplier = db.get(Partner, fornitore_id)
    if not supplier:
        return JSONResponse(status_code=404, content={"error": "Fornitore non trovato"})

    items_data = data.get('items', [])
    if not items_data:
        return JSONResponse(status_code=400, content={"error": "Almeno una riga merce richiesta"})

    doc_date_str = data.get('data_documento')
    doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()
    ric_date_str = data.get('data_ricezione')
    ric_date = datetime.strptime(ric_date_str, '%Y-%m-%d').date() if ric_date_str else date.today()

    totale_imponibile = 0.0
    totale_colli = 0
    totale_peso_netto = 0.0
    purchase_items = []

    for it in items_data:
        prod_id = it.get('product_id')
        product = db.get(Product, prod_id) if prod_id else None
        if not product:
            return JSONResponse(status_code=404, content={"error": f"Prodotto ID {prod_id} non trovato"})

        lotto = it.get('lotto')
        scadenza_str = it.get('data_scadenza')
        scadenza_date = datetime.strptime(scadenza_str, '%Y-%m-%d').date() if scadenza_str else None

        if product.in_scadenza:
            if not lotto or not str(lotto).strip():
                return JSONResponse(status_code=400, content={"error": f"Il lotto è obbligatorio per l'articolo biologico '{product.descrizione}'"})
            if not scadenza_date:
                return JSONResponse(status_code=400, content={"error": f"La data di scadenza è obbligatoria per l'articolo biologico '{product.descrizione}'"})

        colli = int(it.get('colli', 1))
        qta = float(it.get('quantita', 1.0))
        prezzo = float(it.get('prezzo_unitario', product.prezzo_acquisto if product else 0.0))
        aliquota = int(it.get('aliquota_iva', product.aliquota_iva if product else 4))

        if prezzo > 0:
            product.prezzo_acquisto = prezzo

        totale_imponibile += round(qta * prezzo, 2)
        totale_colli += colli
        totale_peso_netto += qta

        purchase_items.append(PurchaseDeliveryNoteItem(
            product_id=prod_id,
            descrizione=it.get('descrizione', product.descrizione),
            unita_misura=it.get('unita_misura', product.unita_misura),
            colli=colli,
            quantita=qta,
            prezzo_unitario=prezzo,
            aliquota_iva=aliquota,
            lotto=lotto,
            data_scadenza=scadenza_date
        ))

    purchase = PurchaseDeliveryNote(
        numero_documento_fornitore=num_doc,
        data_documento=doc_date,
        data_ricezione=ric_date,
        fornitore_id=supplier.id,
        colli_totali=totale_colli,
        peso_totale_netto=round(totale_peso_netto, 2),
        totale_imponibile=round(totale_imponibile, 2),
        note=data.get('note'),
        items=purchase_items
    )
    db.add(purchase)
    try:
        db.commit()
        db.refresh(purchase)

        # Dispatch evento su Event Bus
        try:
            dispatch_event(
                azione="carico_merci",
                titolo=f"Carico Merci Fornitore {purchase.numero_documento_fornitore}",
                descrizione=f"Registrata entrata merci da fornitore {supplier.ragione_sociale}",
                channel_code="AUDIT",
                category_code="ACQUISTI",
                entita_tipo="purchase_delivery_note",
                entita_id=purchase.id,
                partner_id=supplier.id,
                db=db
            )
        except Exception:
            pass

        return JSONResponse(status_code=201, content=purchase.to_dict())
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"error": str(e)})

@router.get("/purchases/{pid}/labels")
def get_purchase_labels(
    pid: int,
    layout: Optional[str] = "pallet",
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    pnote = db.get(PurchaseDeliveryNote, pid)
    if not pnote:
        return JSONResponse(status_code=404, content={"error": "Purchase delivery note not found"})

    labels = []
    for it in pnote.items:
        lbl = BarcodeLabelService.generate_label(
            sku=it.product.codice if it.product else "ART-BIO",
            description=it.descrizione,
            lot=it.lotto or "L-GEN",
            expiry_date=it.data_scadenza.isoformat() if it.data_scadenza else None,
            quantity=it.quantita,
            weight_net=it.quantita,
            unit=it.unita_misura,
            document_ref=f"CARICO-{pnote.numero_documento_fornitore}",
            recipient_name=pnote.fornitore.ragione_sociale if pnote.fornitore else "Fornitore",
            layout=layout
        )
        labels.append(lbl)

    return {"purchase_id": pnote.id, "count": len(labels), "labels": labels}

@router.get("/warehouse/stock")
def get_warehouse_stock(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    carichi = db.query(
        PurchaseDeliveryNoteItem.product_id,
        PurchaseDeliveryNoteItem.lotto,
        PurchaseDeliveryNoteItem.data_scadenza,
        func.sum(PurchaseDeliveryNoteItem.quantita).label('carico_kg'),
        func.sum(PurchaseDeliveryNoteItem.colli).label('carico_colli')
    ).group_by(
        PurchaseDeliveryNoteItem.product_id,
        PurchaseDeliveryNoteItem.lotto,
        PurchaseDeliveryNoteItem.data_scadenza
    ).all()

    scarichi_ddt = db.query(
        DeliveryNoteItem.product_id,
        DeliveryNoteItem.lotto,
        func.sum(DeliveryNoteItem.quantita).label('scarico_kg'),
        func.sum(DeliveryNoteItem.colli).label('scarico_colli')
    ).group_by(
        DeliveryNoteItem.product_id,
        DeliveryNoteItem.lotto
    ).all()

    scarichi_map = {}
    for s in scarichi_ddt:
        key = (s.product_id, s.lotto)
        scarichi_map[key] = {
            'kg': float(s.scarico_kg or 0.0),
            'colli': int(s.scarico_colli or 0)
        }

    stock_list = []
    today = date.today()

    for c in carichi:
        scaricato = scarichi_map.get((c.product_id, c.lotto), {'kg': 0.0, 'colli': 0})
        giacenza_kg = round(float(c.carico_kg or 0.0) - scaricato['kg'], 2)
        colli_disp = max(0, int(c.carico_colli or 0) - scaricato['colli'])

        if giacenza_kg > 0:
            prod = db.get(Product, c.product_id)
            giorni_a_scadere = (c.data_scadenza - today).days if c.data_scadenza else None
            stato_scadenza = 'ok'
            if giorni_a_scadere is not None:
                if giorni_a_scadere < 0:
                    stato_scadenza = 'scaduto'
                elif giorni_a_scadere <= 7:
                    stato_scadenza = 'urgente'

            stock_list.append({
                "product_id": c.product_id,
                "product_codice": prod.codice if prod else "",
                "product_descrizione": prod.descrizione if prod else "",
                "lotto": c.lotto,
                "data_scadenza": c.data_scadenza.isoformat() if c.data_scadenza else None,
                "giorni_a_scadere": giorni_a_scadere,
                "stato_scadenza": stato_scadenza,
                "giacenza_kg": giacenza_kg,
                "colli_disponibili": colli_disp
            })

    stock_list.sort(key=lambda s: (s['product_codice'], s['data_scadenza'] or '9999-12-31'))
    return stock_list

@router.get("/warehouse/fefo-suggestions")
def get_fefo_suggestions(
    product_id: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    carichi = db.query(
        PurchaseDeliveryNoteItem.product_id,
        PurchaseDeliveryNoteItem.lotto,
        PurchaseDeliveryNoteItem.data_scadenza,
        func.sum(PurchaseDeliveryNoteItem.quantita).label('carico_kg'),
        func.sum(PurchaseDeliveryNoteItem.colli).label('carico_colli')
    ).filter_by(product_id=product_id).group_by(
        PurchaseDeliveryNoteItem.product_id,
        PurchaseDeliveryNoteItem.lotto,
        PurchaseDeliveryNoteItem.data_scadenza
    ).order_by(
        PurchaseDeliveryNoteItem.data_scadenza.asc()
    ).all()

    scarichi_ddt = db.query(
        DeliveryNoteItem.lotto,
        func.sum(DeliveryNoteItem.quantita).label('scarico_kg'),
        func.sum(DeliveryNoteItem.colli).label('scarico_colli')
    ).filter_by(product_id=product_id).group_by(
        DeliveryNoteItem.lotto
    ).all()

    scarichi_map = {s.lotto: {'kg': float(s.scarico_kg or 0.0), 'colli': int(s.scarico_colli or 0)} for s in scarichi_ddt}

    suggestions = []
    first = True
    for c in carichi:
        scaricato = scarichi_map.get(c.lotto, {'kg': 0.0, 'colli': 0})
        giacenza_kg = round(float(c.carico_kg or 0.0) - scaricato['kg'], 2)
        colli_disp = max(0, int(c.carico_colli or 0) - scaricato['colli'])

        if giacenza_kg > 0:
            suggestions.append({
                "product_id": c.product_id,
                "lotto": c.lotto,
                "data_scadenza": c.data_scadenza.isoformat() if c.data_scadenza else None,
                "giacenza_kg": giacenza_kg,
                "colli_disponibili": colli_disp,
                "consigliato_fefo": first
            })
            first = False

    return suggestions
