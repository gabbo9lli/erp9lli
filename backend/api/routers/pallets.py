from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from models import PalletType, PalletReceipt, Partner, User
from api.deps import require_auth
from services.pallet_service import PalletService
from schemas.pallet import PalletTypeResponse, PalletReceiptResponse, PalletLedgerItemResponse

router = APIRouter(prefix="/api/pallets", tags=["Pallets L. 182/2025"])

@router.get("/types", response_model=List[PalletTypeResponse])
def get_pallet_types(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    PalletService.seed_default_pallet_types(db)
    types = db.query(PalletType).filter_by(attivo=True).order_by(PalletType.codice.asc()).all()
    return types

@router.post("/types", response_model=PalletTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_pallet_type(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    codice = data.get('codice')
    descrizione = data.get('descrizione')
    if not codice or not descrizione:
        raise HTTPException(status_code=400, detail="codice e descrizione sono obbligatori")
    pt = PalletType(
        codice=codice,
        descrizione=descrizione,
        materiale=data.get('materiale', 'legno'),
        valore_risarcimento=float(data.get('valore_risarcimento', 18.0)),
        attivo=data.get('attivo', True)
    )
    db.add(pt)
    db.commit()
    db.refresh(pt)
    return pt

@router.get("/receipts", response_model=List[PalletReceiptResponse])
def get_pallet_receipts(
    partner_id: Optional[int] = None,
    stato: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    query = db.query(PalletReceipt)
    if partner_id:
        query = query.filter_by(partner_id=partner_id)
    if stato and stato != 'tutti':
        query = query.filter_by(stato=stato)
    if search:
        search_filter = f"%{search}%"
        query = query.join(PalletReceipt.partner).filter(
            (PalletReceipt.numero_completo.ilike(search_filter)) |
            (Partner.ragione_sociale.ilike(search_filter))
        )
    receipts = query.order_by(PalletReceipt.data_emissione.desc(), PalletReceipt.numero.desc()).all()
    return receipts

@router.get("/receipts/{pid}", response_model=PalletReceiptResponse)
def get_pallet_receipt_detail(
    pid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    receipt = db.get(PalletReceipt, pid)
    if not receipt:
        raise HTTPException(status_code=404, detail="Pallet receipt not found")
    return receipt

@router.post("/receipts", response_model=PalletReceiptResponse, status_code=status.HTTP_201_CREATED)
async def create_pallet_receipt(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    return PalletService.create_pallet_receipt(db, data)

@router.post("/receipts/{pid}/return", response_model=PalletReceiptResponse)
async def return_pallet_receipt(
    pid: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    return PalletService.return_pallet_receipt(db, pid, data)

@router.get("/ledger", response_model=List[PalletLedgerItemResponse])
def get_pallets_ledger(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    return PalletService.get_pallets_ledger(db)

@router.post("/receipts/{pid}/invoice-unreturned", status_code=status.HTTP_201_CREATED)
def invoice_unreturned_pallets(
    pid: int,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    invoice = PalletService.invoice_unreturned_pallets(db, pid)
    return JSONResponse(status_code=201, content=invoice.to_dict())

@router.post("/batch-solleciti", status_code=status.HTTP_202_ACCEPTED)
def batch_solleciti_pallets(
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    today = date.today()
    expired_receipts = db.query(PalletReceipt).filter(
        PalletReceipt.stato == 'aperto',
        PalletReceipt.data_limite_restituzione < today
    ).all()

    desc = f"Avvio solleciti massivi per {len(expired_receipts)} buoni pallet scaduti oltre i termini di legge."

    def _process_solleciti(event):
        import time
        totale = len(expired_receipts)
        for i, r in enumerate(expired_receipts):
            time.sleep(0.01)
            event.progresso = int(((i + 1) / max(1, totale)) * 100)
            db.commit()

    from services.event_dispatcher import dispatch_event
    ev = dispatch_event(
        channel_code="EMAIL",
        category_code="PALLET",
        azione="sollecito_massivo_pallet",
        titolo="Sollecito Massivo Buoni Pallet Scaduti",
        descrizione=desc,
        payload_dati={"conteggio_scaduti": len(expired_receipts)},
        is_async=True,
        target_func=_process_solleciti,
        db=db
    )
    return JSONResponse(status_code=202, content=ev.to_dict())
