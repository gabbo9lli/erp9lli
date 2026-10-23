from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Partner, User
from api.deps import require_auth
from schemas.partner import PartnerCreate, PartnerUpdate, PartnerResponse

router = APIRouter(prefix="/api/partners", tags=["Partners"])

@router.get("", response_model=List[PartnerResponse])
def get_partners(
    tipo: Optional[str] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    query = db.query(Partner)
    if tipo:
        query = query.filter((Partner.tipo == tipo) | (Partner.tipo == 'entrambi'))
    return query.all()

@router.post("", response_model=PartnerResponse, status_code=status.HTTP_201_CREATED)
def create_partner(
    payload: PartnerCreate,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = payload.model_dump(exclude_unset=True)
    partner = Partner(**data)
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner

@router.get("/{partner_id}", response_model=PartnerResponse)
def get_partner(
    partner_id: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    partner = db.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    return partner

@router.put("/{partner_id}", response_model=PartnerResponse)
def update_partner(
    partner_id: int,
    payload: PartnerUpdate,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    partner = db.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(partner, key, value)

    db.commit()
    db.refresh(partner)
    return partner

@router.delete("/{partner_id}")
def delete_partner(
    partner_id: int,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    partner = db.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    partner.attivo = False
    db.commit()
    return {"message": "Partner deactivated successfully"}
