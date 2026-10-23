import os
from typing import List
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from models import EcommerceSyncLog, User
from api.deps import require_auth
from services.ecommerce_service import EcommerceService
from core.config import settings
from schemas.ecommerce import EcommerceSyncLogResponse, StockFeedItemResponse

router = APIRouter(prefix="/api/ecommerce", tags=["E-Commerce"])

@router.post("/webhook/orders")
async def handle_ecommerce_order_webhook(request: Request, db: Session = Depends(get_db)):
    expected_secret = settings.ECOMMERCE_WEBHOOK_SECRET
    provided_secret = request.headers.get("X-Ecommerce-Secret")
    auth_email = request.headers.get("X-Forwarded-Email")

    if not auth_email and provided_secret != expected_secret:
        return JSONResponse(
            status_code=401,
            content={"error": "Non autorizzato: token webhook e-commerce non valido"}
        )

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    try:
        order, is_new = EcommerceService.process_incoming_order(db=db, payload=payload)
        status_code = 201 if is_new else 200
        return JSONResponse(status_code=status_code, content=order.to_dict())
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Errore importazione ordine: {str(e)}"})

@router.get("/sync/stock", response_model=List[StockFeedItemResponse])
def get_ecommerce_stock_feed(current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    feed = EcommerceService.get_stock_sync_feed(db=db)
    return feed

@router.get("/logs", response_model=List[EcommerceSyncLogResponse])
def get_ecommerce_sync_logs(current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    logs = db.query(EcommerceSyncLog).order_by(EcommerceSyncLog.id.desc()).limit(100).all()
    return logs
