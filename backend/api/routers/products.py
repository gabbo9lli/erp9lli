from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Product, User
from api.deps import require_auth
from schemas.product import ProductCreate, ProductUpdate, ProductResponse

router = APIRouter(prefix="/api/products", tags=["Products"])

@router.get("", response_model=List[ProductResponse])
def get_products(
    categoria: Optional[str] = None,
    in_scadenza: Optional[bool] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    query = db.query(Product).filter_by(attivo=True)
    if categoria:
        query = query.filter(Product.categoria == categoria)
    if in_scadenza is not None:
        query = query.filter(Product.in_scadenza == in_scadenza)
    if search:
        s = f"%{search}%"
        query = query.filter((Product.codice.ilike(s)) | (Product.descrizione.ilike(s)))
    return query.all()

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    existing = db.query(Product).filter_by(codice=payload.codice).first()
    if existing:
        return JSONResponse(
            status_code=400,
            content={"error": f"Product with code '{payload.codice}' already exists"}
        )

    data = payload.model_dump(exclude_unset=True)
    product = Product(**data)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return product

@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.attivo = False
    db.commit()
    return {"message": "Product deactivated successfully"}
