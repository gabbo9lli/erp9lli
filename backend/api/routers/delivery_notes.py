from typing import Optional, List
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
from models import DeliveryNote, Partner, User
from api.deps import require_auth
from schemas.delivery_note import DeliveryNoteResponse
from services.delivery_note_service import DeliveryNoteService
from services.barcode_label_service import BarcodeLabelService

router = APIRouter(prefix="/api/delivery-notes", tags=["DeliveryNotes"])

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
    return DeliveryNoteService.create_delivery_note(db, data)

@router.put("/{did}", response_model=DeliveryNoteResponse)
async def update_delivery_note(
    did: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    return DeliveryNoteService.update_delivery_note(db, did, data)

@router.delete("/{did}")
def delete_delivery_note(
    did: int,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    DeliveryNoteService.delete_delivery_note(db, did)
    return {"message": "Delivery note deleted"}

@router.post("/{did}/confirm", response_model=DeliveryNoteResponse)
def confirm_delivery_note(
    did: int,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    return DeliveryNoteService.confirm_delivery_note(db, did)

@router.get("/{did}/labels")
def get_delivery_note_labels(
    did: int,
    type: Optional[str] = "pallet",
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    ddt = db.get(DeliveryNote, did)
    if not ddt:
        raise HTTPException(status_code=404, detail="Delivery note not found")

    labels = []
    for item in ddt.items:
        lbl = BarcodeLabelService.generate_label(
            sku=item.product.codice if item.product else "ART",
            description=item.descrizione,
            lot=item.lotto or "L-00",
            expiry_date=item.data_scadenza.isoformat() if item.data_scadenza else None,
            quantity=item.colli,
            weight_net=item.quantita,
            unit=item.unita_misura,
            document_ref=ddt.numero_completo,
            recipient_name=ddt.cliente.ragione_sociale if ddt.cliente else "Cliente",
            layout=type
        )
        labels.append(lbl)

    return {"ddt_id": ddt.id, "count": len(labels), "labels": labels}
