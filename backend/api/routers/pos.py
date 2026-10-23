from typing import Optional, List
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from models import PosStation, PosSale, User
from api.deps import require_auth
from services.pos_sale_service import PosSaleService
from schemas.pos import PosStationResponse, PosSaleResponse

router = APIRouter(prefix="/api/pos", tags=["POS BancoM"])

@router.get("/stations", response_model=List[PosStationResponse])
def get_pos_stations(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    PosSaleService.seed_default_pos_stations(db)
    stations = db.query(PosStation).order_by(PosStation.id.asc()).all()
    return stations

@router.post("/stations", response_model=PosStationResponse, status_code=status.HTTP_201_CREATED)
async def create_pos_station(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    codice = (data.get('codice') or '').strip().upper()
    nome = (data.get('nome') or '').strip()
    if not codice or not nome:
        raise HTTPException(status_code=400, detail="codice e nome sono obbligatori")
    st = PosStation(
        codice=codice,
        nome=nome,
        driver_tipo=data.get('driver_tipo', 'simulator'),
        ip_address=data.get('ip_address'),
        porta=int(data.get('porta', 80)),
        matricola_rt=data.get('matricola_rt'),
        intestazione=data.get('intestazione'),
        pie_pagina=data.get('pie_pagina'),
        attivo=data.get('attivo', True)
    )
    db.add(st)
    db.commit()
    db.refresh(st)
    return st

@router.put("/stations/{sid}", response_model=PosStationResponse)
async def update_pos_station(
    sid: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    st = db.get(PosStation, sid)
    if not st:
        raise HTTPException(status_code=404, detail="Punto cassa non trovato")
    data = await request.json()
    for field in ['nome', 'driver_tipo', 'ip_address', 'porta', 'matricola_rt', 'intestazione', 'pie_pagina', 'attivo']:
        if field in data:
            setattr(st, field, data[field])
    db.commit()
    db.refresh(st)
    return st

@router.get("/sales", response_model=List[PosSaleResponse])
def get_pos_sales(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    PosSaleService.seed_default_pos_stations(db)
    sales = db.query(PosSale).order_by(PosSale.id.desc()).limit(100).all()
    return sales

@router.post("/sales", response_model=PosSaleResponse, status_code=status.HTTP_201_CREATED)
async def create_pos_sale(
    request: Request,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    data = await request.json()
    sale, ticket_res = PosSaleService.create_pos_sale(db, data, current_user)
    resp_data = sale.to_dict()
    resp_data["ticket_ascii"] = ticket_res.get("ticket_ascii")
    return JSONResponse(status_code=201, content=resp_data)

@router.post("/sales/{sid}/print")
def print_pos_sale(
    sid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    return PosSaleService.print_pos_sale(db, sid)
