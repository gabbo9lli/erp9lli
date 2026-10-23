from typing import Optional, List
from fastapi import APIRouter, Request, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from database import get_db
from models import Invoice, InvoiceInstallment, Partner, User
from api.deps import require_auth
from schemas.invoice import InvoiceResponse, InvoiceInstallmentResponse
from services.invoice_service import InvoiceService
from services.sdi_service import generate_sdi_xml, validate_sdi_invoice

router = APIRouter(prefix="/api", tags=["Invoices & SDI"])

@router.get("/invoices", response_model=List[InvoiceResponse])
def get_invoices(
    stato: Optional[str] = None,
    tipo: Optional[str] = None,
    cliente_id: Optional[int] = None,
    anno: Optional[int] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    query = db.query(Invoice)
    if stato and stato != 'tutti':
        query = query.filter(Invoice.stato == stato)
    if tipo and tipo != 'tutti':
        query = query.filter(Invoice.tipo_documento == tipo)
    if cliente_id:
        query = query.filter(Invoice.cliente_id == cliente_id)
    if anno:
        query = query.filter(Invoice.anno == anno)
    if search:
        search_filter = f"%{search}%"
        query = query.join(Invoice.cliente).filter(
            (Invoice.numero_completo.ilike(search_filter)) |
            (Partner.ragione_sociale.ilike(search_filter))
        )
    invoices = query.order_by(Invoice.data_documento.desc(), Invoice.numero.desc()).all()
    return invoices

@router.get("/invoices/{iid}", response_model=InvoiceResponse)
def get_invoice_detail(
    iid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    invoice = db.get(Invoice, iid)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.post("/invoices/from-ddt", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice_from_ddt(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    ddt_id = data.get('delivery_note_id')
    if not ddt_id:
        raise HTTPException(status_code=400, detail="delivery_note_id is required")
    return InvoiceService.create_invoice_from_ddt(db, ddt_id)

@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice_direct(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    return InvoiceService.create_invoice_direct(db, data)

@router.post("/invoices/{iid}/credit-note", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_credit_note_from_invoice(
    iid: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    return InvoiceService.create_credit_note(db, iid, data)

@router.get("/invoices/{iid}/sdi-validate")
def validate_sdi_invoice_endpoint(
    iid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    invoice = db.get(Invoice, iid)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    res = validate_sdi_invoice(invoice)
    return res

@router.get("/invoices/{iid}/xml")
def download_sdi_xml_endpoint(
    iid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    invoice = db.get(Invoice, iid)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        xml_content, filename = generate_sdi_xml(invoice, db=db)
        return Response(
            content=xml_content,
            media_type="application/xml; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/installments", response_model=List[InvoiceInstallmentResponse])
def get_installments(
    stato: Optional[str] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    query = db.query(InvoiceInstallment)
    if stato and stato != 'tutti':
        query = query.filter_by(stato=stato)
    installments = query.order_by(InvoiceInstallment.data_scadenza.asc()).all()
    return installments

@router.post("/installments/{inst_id}/pay", response_model=InvoiceInstallmentResponse)
def pay_installment(
    inst_id: int,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    return InvoiceService.pay_installment(db, inst_id)
