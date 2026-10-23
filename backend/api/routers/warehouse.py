from typing import Optional, List
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
from models import PurchaseDeliveryNote, User
from api.deps import require_auth
from services.warehouse_service import WarehouseService
from schemas.warehouse import PurchaseDeliveryNoteResponse, StockItemResponse, FefoSuggestionResponse

router = APIRouter(prefix="/api", tags=["Warehouse & Purchases"])

@router.get("/purchases", response_model=List[PurchaseDeliveryNoteResponse])
def get_purchases(
    fornitore_id: Optional[int] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    query = db.query(PurchaseDeliveryNote)
    if fornitore_id:
        query = query.filter_by(fornitore_id=fornitore_id)
    purchases = query.order_by(PurchaseDeliveryNote.data_ricezione.desc(), PurchaseDeliveryNote.id.desc()).all()
    return purchases

@router.get("/purchases/{pid}", response_model=PurchaseDeliveryNoteResponse)
def get_purchase_detail(
    pid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    purchase = db.get(PurchaseDeliveryNote, pid)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase delivery note not found")
    return purchase

@router.post("/purchases", response_model=PurchaseDeliveryNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    return WarehouseService.create_purchase(db, data)

@router.get("/purchases/{pid}/labels")
def get_purchase_labels(
    pid: int,
    layout: Optional[str] = "pallet",
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    return WarehouseService.get_purchase_labels(db, pid, layout)

@router.get("/warehouse/stock", response_model=List[StockItemResponse])
def get_warehouse_stock(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    return WarehouseService.get_warehouse_stock(db)

@router.get("/warehouse/fefo-suggestions", response_model=List[FefoSuggestionResponse])
def get_fefo_suggestions(
    product_id: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    return WarehouseService.get_fefo_suggestions(db, product_id)
