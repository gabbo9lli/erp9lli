from typing import Optional, List
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from models import CmrDocument, Partner, User
from api.deps import require_auth
from services.cmr_service import CmrService
from schemas.cmr import CmrDocumentResponse

router = APIRouter(prefix="/api/cmr", tags=["CMR Export"])

@router.get("", response_model=List[CmrDocumentResponse])
def get_cmr_documents(
    cliente_id: Optional[int] = None,
    vettore_id: Optional[int] = None,
    anno: Optional[int] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    query = db.query(CmrDocument)
    if cliente_id:
        query = query.filter_by(cliente_id=cliente_id)
    if vettore_id:
        query = query.filter_by(vettore_id=vettore_id)
    if anno:
        query = query.filter_by(anno=anno)
    if search:
        search_filter = f"%{search}%"
        query = query.join(CmrDocument.cliente).filter(
            (CmrDocument.numero_completo.ilike(search_filter)) |
            (Partner.ragione_sociale.ilike(search_filter)) |
            (CmrDocument.luogo_consegna.ilike(search_filter))
        )
    documents = query.order_by(CmrDocument.data_documento.desc(), CmrDocument.numero.desc()).all()
    return documents

@router.get("/{cid}", response_model=CmrDocumentResponse)
def get_cmr_detail(
    cid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    cmr = db.get(CmrDocument, cid)
    if not cmr:
        raise HTTPException(status_code=404, detail="CMR not found")
    return cmr

@router.post("/from-ddt/{ddt_id}", response_model=CmrDocumentResponse, status_code=status.HTTP_201_CREATED)
def create_cmr_from_ddt(
    ddt_id: int,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    return CmrService.create_cmr_from_ddt(db, ddt_id)

@router.post("", response_model=CmrDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_cmr_manual(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    return CmrService.create_cmr_manual(db, data)

@router.put("/{cid}", response_model=CmrDocumentResponse)
async def update_cmr(
    cid: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    return CmrService.update_cmr(db, cid, data)

@router.get("/{cid}/print")
def get_cmr_print_format(
    cid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    return CmrService.get_cmr_print_format(db, cid)
