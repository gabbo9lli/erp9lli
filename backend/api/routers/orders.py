from typing import Optional, List
from datetime import datetime, date
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import CustomerOrder, OrderItem, DeliveryNote, DeliveryNoteItem, Partner, Product, User
from api.deps import require_auth
from services.event_dispatcher import dispatch_event

router = APIRouter(prefix="/api/orders", tags=["Orders"])

def get_next_order_number(anno: int, db: Session) -> int:
    max_num = db.query(func.max(CustomerOrder.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

def get_next_ddt_number(anno: int, db: Session) -> int:
    max_num = db.query(func.max(DeliveryNote.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

@router.get("")
def get_orders(
    stato: Optional[str] = None,
    cliente_id: Optional[int] = None,
    anno: Optional[int] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    query = db.query(CustomerOrder)
    if stato and stato != 'tutti':
        query = query.filter(CustomerOrder.stato == stato)
    if cliente_id:
        query = query.filter(CustomerOrder.cliente_id == cliente_id)
    if anno:
        query = query.filter(CustomerOrder.anno == anno)
    if search:
        search_filter = f"%{search}%"
        query = query.join(CustomerOrder.cliente).filter(
            (CustomerOrder.numero_completo.ilike(search_filter)) |
            (Partner.ragione_sociale.ilike(search_filter))
        )
    orders = query.order_by(CustomerOrder.data_ordine.desc(), CustomerOrder.numero.desc()).all()
    return [o.to_dict() for o in orders]

@router.get("/{oid}")
def get_order_detail(
    oid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    order = db.get(CustomerOrder, oid)
    if not order:
        return JSONResponse(status_code=404, content={"error": "Order not found"})
    return order.to_dict()

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_order(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    cliente_id = data.get('cliente_id')
    if not cliente_id:
        return JSONResponse(status_code=400, content={"error": "cliente_id is required"})
    cliente = db.get(Partner, cliente_id)
    if not cliente:
        return JSONResponse(status_code=404, content={"error": "Cliente not found"})

    items_data = data.get('items', [])
    if not items_data:
        return JSONResponse(status_code=400, content={"error": "At least one item is required"})

    doc_date_str = data.get('data_ordine')
    doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()
    req_date_str = data.get('data_richiesta')
    req_date = datetime.strptime(req_date_str, '%Y-%m-%d').date() if req_date_str else None
    conf_date_str = data.get('data_confermata')
    conf_date = datetime.strptime(conf_date_str, '%Y-%m-%d').date() if conf_date_str else None

    anno = doc_date.year
    numero = get_next_order_number(anno, db)
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
    try:
        db.commit()
        db.refresh(order)
        return JSONResponse(status_code=201, content=order.to_dict())
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"error": str(e)})

@router.put("/{oid}")
async def update_order(
    oid: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    order = db.get(CustomerOrder, oid)
    if not order:
        return JSONResponse(status_code=404, content={"error": "Order not found"})
    if order.stato == 'chiuso':
        return JSONResponse(status_code=400, content={"error": "Impossibile modificare un ordine chiuso"})

    data = await request.json()
    if 'note' in data:
        order.note = data['note']
    if 'data_richiesta' in data:
        order.data_richiesta = datetime.strptime(data['data_richiesta'], '%Y-%m-%d').date() if data['data_richiesta'] else None
    if 'data_confermata' in data:
        order.data_confermata = datetime.strptime(data['data_confermata'], '%Y-%m-%d').date() if data['data_confermata'] else None

    try:
        db.commit()
        db.refresh(order)
        return order.to_dict()
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"error": str(e)})

@router.post("/{oid}/fulfill-to-ddt", status_code=status.HTTP_201_CREATED)
async def fulfill_order_to_ddt(
    oid: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    order = db.get(CustomerOrder, oid)
    if not order:
        return JSONResponse(status_code=404, content={"error": "Order not found"})
    if order.stato == 'chiuso':
        return JSONResponse(status_code=400, content={"error": "L'ordine è già interamente chiuso"})

    data = await request.json()
    items_to_fulfill = data.get('items', [])
    if not items_to_fulfill:
        items_to_fulfill = [
            {"order_item_id": it.id, "colli": it.colli_residui, "quantita": it.quantita_residua}
            for it in order.items if it.quantita_residua > 0
        ]

    ddt_date = date.today()
    ddt_anno = ddt_date.year
    ddt_num = get_next_ddt_number(ddt_anno, db)
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
        return JSONResponse(status_code=400, content={"error": "Nessuna quantità valida da evadere"})

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

    try:
        db.commit()
        db.refresh(order)
        db.refresh(ddt)
        return JSONResponse(
            status_code=201,
            content={
                "message": f"DDT {ddt.numero_completo} generato con successo",
                "ddt": ddt.to_dict(),
                "order": order.to_dict()
            }
        )
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"error": str(e)})
