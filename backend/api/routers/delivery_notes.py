from typing import Optional, List
from datetime import datetime, date
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import DeliveryNote, DeliveryNoteItem, Partner, Product, User
from api.deps import require_auth
from services.barcode_label_service import BarcodeLabelService
from services.event_dispatcher import dispatch_event
from schemas.delivery_note import DeliveryNoteResponse

router = APIRouter(prefix="/api/delivery-notes", tags=["DeliveryNotes"])

def get_next_ddt_number(anno: int, db: Session) -> int:
    max_num = db.query(func.max(DeliveryNote.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

@router.get("", response_model=List[DeliveryNoteResponse])
def get_delivery_notes(
    stato: Optional[str] = None,
    cliente_id: Optional[int] = None,
    anno: Optional[int] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    query = db.query(DeliveryNote)
    if stato and stato != 'tutti':
        query = query.filter(DeliveryNote.stato == stato)
    if cliente_id:
        query = query.filter(DeliveryNote.cliente_id == cliente_id)
    if anno:
        query = query.filter(DeliveryNote.anno == anno)
    if search:
        search_filter = f"%{search}%"
        query = query.join(DeliveryNote.cliente).filter(
            (DeliveryNote.numero_completo.ilike(search_filter)) |
            (Partner.ragione_sociale.ilike(search_filter))
        )
    ddts = query.order_by(DeliveryNote.data_documento.desc(), DeliveryNote.numero.desc()).all()
    return ddts

@router.get("/unbilled", response_model=List[DeliveryNoteResponse])
def get_unbilled_delivery_notes(
    cliente_id: Optional[int] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    # DDT confermati ma non ancora associati ad una fattura
    query = db.query(DeliveryNote).filter(DeliveryNote.stato == 'confermato')
    if cliente_id:
        query = query.filter(DeliveryNote.cliente_id == cliente_id)
    ddts = [d for d in query.all() if not getattr(d, 'invoice_id', None)]
    return ddts

@router.get("/{did}", response_model=DeliveryNoteResponse)
def get_delivery_note_detail(
    did: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    ddt = db.get(DeliveryNote, did)
    if not ddt:
        raise HTTPException(status_code=404, detail="Delivery note not found")
    return ddt

@router.post("", response_model=DeliveryNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_delivery_note(
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
        return JSONResponse(status_code=400, content={"error": "Cliente partner not found"})

    items_data = data.get('items', [])
    if not items_data:
        return JSONResponse(status_code=400, content={"error": "At least one item is required in delivery note"})

    doc_date_str = data.get('data_documento')
    if doc_date_str:
        doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date()
    else:
        doc_date = date.today()

    anno = doc_date.year
    numero = get_next_ddt_number(anno, db)
    numero_completo = f"DDT-{anno}-{numero:04d}"

    colli_totali = 0
    peso_totale_netto = 0.0
    peso_totale_lordo = 0.0
    totale_imponibile = 0.0

    ddt_items = []
    for idx, item in enumerate(items_data):
        prod_id = item.get('product_id')
        if not prod_id:
            return JSONResponse(status_code=400, content={"error": f"Item {idx+1}: product_id is required"})
        product = db.get(Product, prod_id)
        if not product:
            return JSONResponse(status_code=400, content={"error": f"Item {idx+1}: product not found"})

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
                return JSONResponse(
                    status_code=400,
                    content={"error": f"Prodotto biologico in scadenza '{product.descrizione}': lotto e data di scadenza sono obbligatori!"}
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
    try:
        db.commit()
        db.refresh(ddt)
        return ddt
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{did}", response_model=DeliveryNoteResponse)
async def update_delivery_note(
    did: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    ddt = db.get(DeliveryNote, did)
    if not ddt:
        raise HTTPException(status_code=404, detail="Delivery note not found")
    if ddt.stato != 'bozza':
        raise HTTPException(status_code=400, detail=f"Impossibile modificare un DDT in stato '{ddt.stato}' (confermato)")

    data = await request.json()
    for key in ('vettore_id', 'causale_trasporto', 'porto', 'aspetto_beni', 'note'):
        if key in data:
            setattr(ddt, key, data[key])

    try:
        db.commit()
        db.refresh(ddt)
        return ddt
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{did}")
def delete_delivery_note(
    did: int,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    ddt = db.get(DeliveryNote, did)
    if not ddt:
        raise HTTPException(status_code=404, detail="Delivery note not found")
    if ddt.stato != 'bozza':
        raise HTTPException(status_code=400, detail=f"Impossibile eliminare un DDT in stato '{ddt.stato}' (confermato)")

    try:
        db.delete(ddt)
        db.commit()
        return {"message": "Delivery note deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{did}/confirm", response_model=DeliveryNoteResponse)
def confirm_delivery_note(
    did: int,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    ddt = db.get(DeliveryNote, did)
    if not ddt:
        raise HTTPException(status_code=404, detail="Delivery note not found")
    if not ddt.items:
        raise HTTPException(status_code=400, detail="Impossibile confermare un DDT senza righe merce")

    ddt.stato = 'confermato'
    try:
        db.commit()
        db.refresh(ddt)

        # Dispatch evento su Event Bus
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
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{did}/labels")
def get_delivery_note_labels(
    did: int,
    type: Optional[str] = "pallet",
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    ddt = db.get(DeliveryNote, did)
    if not ddt:
        return JSONResponse(status_code=404, content={"error": "DDT non trovato"})

    label_type = (type or 'pallet').lower()
    labels = []

    for item in ddt.items:
        prod = item.product
        data = {
            "descrizione": item.descrizione or (prod.descrizione if prod else "Articolo Bio"),
            "codice_articolo": prod.codice if prod else "ART-BIO",
            "lotto": item.lotto or "LOTTO-DDT",
            "data_scadenza": item.data_scadenza.isoformat() if item.data_scadenza else None,
            "colli": item.colli or 1,
            "peso_netto": float(item.quantita or 0.0),
            "peso_lordo": float(item.quantita or 0.0) + 25.0,
            "tara": 25.0,
            "origine": "Italia",
            "ente_certificatore": getattr(ddt.cliente, 'istituto_certificatore', None) or "IT-BIO-009 CCPB"
        }
        barcode_val = f"{data['codice_articolo']}-{data['lotto']}".replace(" ", "")

        if label_type == 'pallet':
            zpl = BarcodeLabelService.generate_pallet_zpl(data)
            html = BarcodeLabelService.render_pallet_html(data)
            svg = BarcodeLabelService.generate_code128_svg(barcode_val, height=60, bar_width=2)
        else:
            zpl = BarcodeLabelService.generate_collo_zpl(data)
            html = BarcodeLabelService.render_collo_html(data)
            svg = BarcodeLabelService.generate_code128_svg(barcode_val, height=35, bar_width=1)

        labels.append({
            "item_id": item.id,
            "label_type": label_type,
            "barcode_value": barcode_val,
            "zpl": zpl,
            "svg_barcode": svg,
            "html_preview": html,
            "dati": data
        })

    try:
        dispatch_event(
            azione="stampa_etichette_barcode",
            titolo=f"Stampa Etichette DDT {ddt.numero_completo}",
            descrizione=f"Generate {len(labels)} etichette barcode per DDT {ddt.numero_completo}",
            channel_code="AUDIT",
            category_code="LOGISTICA",
            entita_tipo="delivery_note",
            entita_id=ddt.id,
            partner_id=ddt.cliente_id,
            db=db
        )
    except Exception:
        pass

    return {
        "delivery_note_id": ddt.id,
        "count": len(labels),
        "labels": labels
    }
