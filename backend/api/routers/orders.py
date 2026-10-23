from typing import Optional, List
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
from models import CustomerOrder, Partner, User
from api.deps import require_auth
from schemas.order import OrderResponse, OrderFulfillResponse
from services.order_service import OrderService

router = APIRouter(prefix="/api/orders", tags=["Orders"])

@router.get("", response_model=List[OrderResponse])
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
    return orders

@router.get("/{oid}", response_model=OrderResponse)
def get_order_detail(
    oid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    order = db.get(CustomerOrder, oid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    return OrderService.create_order(db, data)

@router.put("/{oid}", response_model=OrderResponse)
async def update_order(
    oid: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    return OrderService.update_order(db, oid, data)

@router.post("/{oid}/fulfill-to-ddt", response_model=OrderFulfillResponse, status_code=status.HTTP_201_CREATED)
async def fulfill_order_to_ddt(
    oid: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    ddt, order = OrderService.fulfill_to_ddt(db, oid, data)
    return {
        "message": "Ordine parzialmente o totalmente evaso a DDT",
        "ddt": ddt,
        "order": order
    }
