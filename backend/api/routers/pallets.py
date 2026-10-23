from typing import Optional, List
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import PalletType, PalletReceipt, PalletReceiptItem, Partner, Product, Invoice, InvoiceItem, InvoiceInstallment, User
from api.deps import require_auth
from api.routers.invoices import get_next_invoice_number, calculate_installments
from schemas.pallet import PalletTypeResponse, PalletReceiptResponse, PalletLedgerItemResponse

router = APIRouter(prefix="/api/pallets", tags=["Pallets L. 182/2025"])

DEFAULT_PALLET_TYPES = [
    {"codice": "EPAL", "descrizione": "EUR/EPAL Standard Legno (80x120 cm)", "materiale": "legno", "valore_risarcimento": 18.0},
    {"codice": "CHEP", "descrizione": "Pallet Blu CHEP Circuito Chiuso (80x120 cm)", "materiale": "legno", "valore_risarcimento": 22.0},
    {"codice": "IFCO", "descrizione": "Cassa Plastica Pieghevole IFCO Green", "materiale": "plastica", "valore_risarcimento": 3.5},
    {"codice": "CPR", "descrizione": "Cassa Plastica Pieghevole CPR System", "materiale": "plastica", "valore_risarcimento": 2.5}
]

def seed_default_pallet_types(db: Session):
    for pt_data in DEFAULT_PALLET_TYPES:
        if not db.query(PalletType).filter_by(codice=pt_data["codice"]).first():
            db.add(PalletType(**pt_data))
    db.commit()

def get_next_pallet_receipt_number(anno: int, db: Session) -> int:
    max_num = db.query(func.max(PalletReceipt.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

@router.get("/types", response_model=List[PalletTypeResponse])
def get_pallet_types(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    seed_default_pallet_types(db)
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
    seed_default_pallet_types(db)
    data = await request.json()
    partner_id = data.get('partner_id')
    if not partner_id:
        return JSONResponse(status_code=400, content={"error": "partner_id is required"})
    partner = db.get(Partner, partner_id)
    if not partner:
        return JSONResponse(status_code=404, content={"error": "Partner not found"})

    items_data = data.get('items', [])
    if not items_data:
        return JSONResponse(status_code=400, content={"error": "Almeno una tipologia pallet richiesta"})

    doc_date_str = data.get('data_emissione')
    doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()

    term_days = int(data.get('termini_giorni', 60))
    limit_date_str = data.get('data_limite_restituzione')
    limit_date = datetime.strptime(limit_date_str, '%Y-%m-%d').date() if limit_date_str else (doc_date + timedelta(days=term_days))

    anno = doc_date.year
    numero = get_next_pallet_receipt_number(anno, db)
    numero_completo = f"BP-{anno}-{numero:04d}"

    totale_consegnati = 0
    totale_restituiti = 0
    receipt_items = []

    for it in items_data:
        pt_id = it.get('pallet_type_id')
        ptype = db.get(PalletType, pt_id) if pt_id else None
        if not ptype:
            return JSONResponse(status_code=404, content={"error": f"PalletType {pt_id} non trovato"})

        q_cons = int(it.get('quantita_consegnata', 0))
        q_rest = int(it.get('quantita_restituita', 0))
        saldo_r = q_cons - q_rest

        totale_consegnati += q_cons
        totale_restituiti += q_rest

        receipt_items.append(PalletReceiptItem(
            pallet_type_id=pt_id,
            quantita_consegnata=q_cons,
            quantita_restituita=q_rest,
            saldo_riga=saldo_r
        ))

    saldo_netto = totale_consegnati - totale_restituiti
    stato = 'saldato' if saldo_netto <= 0 else 'aperto'

    receipt = PalletReceipt(
        numero=numero,
        anno=anno,
        numero_completo=numero_completo,
        data_emissione=doc_date,
        data_limite_restituzione=limit_date,
        partner_id=partner.id,
        delivery_note_id=data.get('delivery_note_id'),
        tipo=data.get('tipo', 'uscita'),
        totale_consegnati=totale_consegnati,
        totale_restituiti=totale_restituiti,
        saldo_netto=saldo_netto,
        stato=stato,
        note=data.get('note'),
        items=receipt_items
    )
    db.add(receipt)
    try:
        db.commit()
        db.refresh(receipt)
        return receipt
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/receipts/{pid}/return", response_model=PalletReceiptResponse)
async def return_pallet_receipt(
    pid: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    receipt = db.get(PalletReceipt, pid)
    if not receipt:
        raise HTTPException(status_code=404, detail="Pallet receipt not found")
    if receipt.stato == 'fatturato':
        raise HTTPException(status_code=400, detail="Impossibile restituire pallet su un buono già fatturato")

    data = await request.json()
    items_returns = data.get('items', [])
    items_map = {it.pallet_type_id: it for it in receipt.items}

    for ret in items_returns:
        pt_id = ret.get('pallet_type_id')
        q_ret = int(ret.get('quantita_restituita', 0))
        item = items_map.get(pt_id)
        if item:
            item.quantita_restituita += q_ret
            item.saldo_riga = item.quantita_consegnata - item.quantita_restituita

    receipt.totale_restituiti = sum(it.quantita_restituita for it in receipt.items)
    receipt.saldo_netto = receipt.totale_consegnati - receipt.totale_restituiti
    if receipt.saldo_netto <= 0:
        receipt.stato = 'saldato'
    else:
        receipt.stato = 'aperto'

    try:
        db.commit()
        db.refresh(receipt)
        return receipt
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/ledger", response_model=List[PalletLedgerItemResponse])
def get_pallets_ledger(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    seed_default_pallet_types(db)
    pallet_types = db.query(PalletType).filter_by(attivo=True).all()
    partners = db.query(Partner).all()

    ledger = []
    today = date.today()

    for p in partners:
        receipts = db.query(PalletReceipt).filter_by(partner_id=p.id).all()
        if not receipts:
            continue

        saldi = {pt.codice: 0 for pt in pallet_types}
        buoni_aperti = 0
        buoni_scaduti = 0

        for r in receipts:
            if r.stato == 'aperto':
                buoni_aperti += 1
                if r.data_limite_restituzione and r.data_limite_restituzione < today:
                    buoni_scaduti += 1

                for it in r.items:
                    if it.pallet_type and it.pallet_type.codice in saldi:
                        saldi[it.pallet_type.codice] += it.saldo_riga

        total_debt = sum(saldi.values())
        if total_debt > 0 or buoni_aperti > 0:
            ledger.append({
                "partner_id": p.id,
                "partner_nome": p.ragione_sociale,
                "partner_tipo": p.tipo,
                "saldi": saldi,
                "totale_bancali_debito": total_debt,
                "buoni_aperti_count": buoni_aperti,
                "buoni_scaduti_count": buoni_scaduti
            })

    ledger.sort(key=lambda x: x['totale_bancali_debito'], reverse=True)
    return ledger

@router.post("/receipts/{pid}/invoice-unreturned", status_code=status.HTTP_201_CREATED)
def invoice_unreturned_pallets(
    pid: int,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    receipt = db.get(PalletReceipt, pid)
    if not receipt:
        return JSONResponse(status_code=404, content={"error": "Pallet receipt not found"})
    if receipt.stato == 'saldato':
        return JSONResponse(status_code=400, content={"error": "Il buono pallet è già saldato"})
    if receipt.stato == 'fatturato':
        return JSONResponse(status_code=400, content={"error": "Il buono pallet è già stato fatturato"})

    items_unreturned = [it for it in receipt.items if it.saldo_riga > 0]
    if not items_unreturned:
        return JSONResponse(status_code=400, content={"error": "Nessun pallet a debito da fatturare"})

    today = date.today()
    anno = today.year
    numero = get_next_invoice_number(anno, db)
    numero_completo = f"FT-{anno}-{numero:04d}"

    totale_imponibile = 0.0
    invoice_items = []

    for it in items_unreturned:
        valore = float(it.pallet_type.valore_risarcimento if it.pallet_type else 18.0)
        qta = float(it.saldo_riga)
        imp_riga = round(qta * valore, 2)
        totale_imponibile += imp_riga

        prod = db.query(Product).filter_by(codice=f"IMB-{it.pallet_type.codice}").first()
        if not prod:
            prod = db.query(Product).filter_by(categoria="imballo").first()
        prod_id = prod.id if prod else 1

        invoice_items.append(InvoiceItem(
            product_id=prod_id,
            descrizione=f"Cessione {it.pallet_type.descrizione} non restituiti ex L. 182/2025 da Buono {receipt.numero_completo}",
            unita_misura="PZ",
            colli=int(qta),
            quantita=qta,
            prezzo_unitario=valore,
            aliquota_iva=0,
            imponibile_riga=imp_riga
        ))

    totale_imponibile = round(totale_imponibile, 2)
    totale_fattura = totale_imponibile

    note_fiscale = (
        f"Fatturazione mancata restituzione pallet ex L. 182/2025 su Buono Pallet {receipt.numero_completo}. "
        "Operazione in Reverse Charge ai sensi dell'Art. 74 comma 7/8 DPR 633/72 per cessione imballaggi usati."
    )

    rate_data = calculate_installments(totale_fattura, today, receipt.partner.condizioni_pagamento or '30gg fm')
    installments = [
        InvoiceInstallment(
            numero_rata=r["numero_rata"],
            totale_rate=r["totale_rate"],
            data_scadenza=r["data_scadenza"],
            importo=r["importo"],
            stato="aperta"
        ) for r in rate_data
    ]

    invoice = Invoice(
        numero=numero,
        anno=anno,
        numero_completo=numero_completo,
        tipo_documento='TD01',
        data_documento=today,
        cliente_id=receipt.partner_id,
        condizioni_pagamento=receipt.partner.condizioni_pagamento or '30gg fm',
        esigibilita_iva='I',
        totale_imponibile=totale_imponibile,
        totale_imposta=0.0,
        totale_fattura=totale_fattura,
        castelletto_iva={"0": {"imponibile": totale_imponibile, "imposta": 0.0}},
        stato='emessa',
        note=note_fiscale,
        items=invoice_items,
        installments=installments
    )
    db.add(invoice)

    receipt.stato = 'fatturato'

    try:
        db.commit()
        db.refresh(invoice)
        return JSONResponse(status_code=201, content=invoice.to_dict())
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"error": str(e)})

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
