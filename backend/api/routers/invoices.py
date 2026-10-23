from typing import Optional, List
from datetime import datetime, date, timedelta
import calendar
from fastapi import APIRouter, Request, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import (
    Invoice, InvoiceItem, InvoiceInstallment, DeliveryNote,
    Partner, Product, User, JournalEntry, JournalItem, AccountingCausal,
    PurchaseDeliveryNote, PurchaseDeliveryNoteItem
)
from api.deps import require_auth
from services.sdi_service import generate_sdi_xml, validate_sdi_invoice
from services.event_dispatcher import dispatch_event
from seed_accounting import seed_default_accounting_causals
from schemas.invoice import InvoiceResponse, InvoiceInstallmentResponse

router = APIRouter(prefix="/api", tags=["Invoices & SDI"])

def get_next_invoice_number(anno: int, db: Session) -> int:
    max_num = db.query(func.max(Invoice.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

def get_next_credit_note_number(anno: int, db: Session) -> int:
    max_num = db.query(func.max(Invoice.numero))\
        .filter(Invoice.anno == anno, Invoice.tipo_documento == 'TD04')\
        .scalar()
    return (max_num or 0) + 1

def get_next_journal_entry_number(anno: int, db: Session) -> int:
    max_num = db.query(func.max(JournalEntry.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

def calculate_installments(totale_fattura: float, data_documento: date, condizioni: Optional[str]) -> list:
    cond = (condizioni or '30gg fm').lower()
    if '30/60/90' in cond:
        giorni_lista = [30, 60, 90]
    elif '30/60' in cond:
        giorni_lista = [30, 60]
    elif '60/90' in cond:
        giorni_lista = [60, 90]
    elif '60' in cond:
        giorni_lista = [60]
    elif '90' in cond:
        giorni_lista = [90]
    elif 'vista' in cond or 'contanti' in cond or 'immediato' in cond:
        giorni_lista = [0]
    else:
        giorni_lista = [30]

    totale_rate = len(giorni_lista)
    base_importo = round(totale_fattura / totale_rate, 2)
    rate = []
    somma_rate = 0.0

    for idx, giorni in enumerate(giorni_lista):
        if giorni == 0:
            scadenza = data_documento
        elif 'fm' in cond or 'fine mese' in cond:
            target_date = data_documento + timedelta(days=giorni)
            _, last_day = calendar.monthrange(target_date.year, target_date.month)
            scadenza = date(target_date.year, target_date.month, last_day)
        else:
            scadenza = data_documento + timedelta(days=giorni)

        if idx == totale_rate - 1:
            importo_rata = round(totale_fattura - somma_rate, 2)
        else:
            importo_rata = base_importo
            somma_rate += importo_rata

        rate.append({
            "numero_rata": idx + 1,
            "totale_rate": totale_rate,
            "data_scadenza": scadenza,
            "importo": importo_rata,
            "stato": "aperta"
        })
    return rate

def auto_post_invoice_to_accounting(inv: Invoice, db: Session):
    seed_default_accounting_causals(db)
    causal = db.query(AccountingCausal).filter_by(codice="VEND_FATT", attivo=True).first()
    if not causal or not (causal.conto_dare_id and causal.conto_avere_id and causal.conto_iva_id):
        return None

    anno = inv.anno or (inv.data_documento.year if inv.data_documento else date.today().year)
    num = get_next_journal_entry_number(anno, db)
    num_comp = f"PN-{anno}-{num:04d}"
    tot_lordo = float(inv.totale_fattura)
    tot_iva = float(inv.totale_imposta or 0.0)
    tot_imp = round(tot_lordo - tot_iva, 2)

    cli_nome = inv.cliente.ragione_sociale if inv.cliente else "Cliente"
    desc_entry = f"Fattura {inv.numero_completo} a {cli_nome}"

    je = JournalEntry(
        numero=num,
        anno=anno,
        numero_completo=num_comp,
        data_registrazione=inv.data_documento or date.today(),
        data_competenza=inv.data_documento or date.today(),
        causale=desc_entry,
        causale_id=causal.id,
        totale_dare=tot_lordo,
        totale_avere=tot_lordo,
        stato="confermata"
    )
    db.add(je)
    db.flush()

    db.add(JournalItem(
        journal_entry_id=je.id,
        account_id=causal.conto_dare_id,
        partner_id=inv.cliente_id,
        descrizione_riga=f"Credito fattura {inv.numero_completo}",
        dare=tot_lordo,
        avere=0.0
    ))
    db.add(JournalItem(
        journal_entry_id=je.id,
        account_id=causal.conto_avere_id,
        descrizione_riga=f"Ricavo vendita {inv.numero_completo}",
        dare=0.0,
        avere=tot_imp
    ))
    db.add(JournalItem(
        journal_entry_id=je.id,
        account_id=causal.conto_iva_id,
        descrizione_riga=f"IVA a debito {inv.numero_completo}",
        dare=0.0,
        avere=tot_iva
    ))
    return je

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
    cliente_id = data.get('cliente_id')
    ddt_ids = data.get('ddt_ids', [])
    if not cliente_id or not ddt_ids:
        return JSONResponse(status_code=400, content={"error": "cliente_id e ddt_ids sono obbligatori"})

    cliente = db.get(Partner, cliente_id)
    if not cliente:
        return JSONResponse(status_code=404, content={"error": "Cliente non trovato"})

    ddts = db.query(DeliveryNote).filter(DeliveryNote.id.in_(ddt_ids)).all()
    if len(ddts) != len(ddt_ids):
        return JSONResponse(status_code=404, content={"error": "Uno o più DDT non trovati"})

    for d in ddts:
        if d.cliente_id != cliente.id:
            return JSONResponse(status_code=400, content={"error": f"DDT {d.numero_completo} non appartiene a questo cliente"})
        if d.stato != 'confermato':
            return JSONResponse(status_code=400, content={"error": f"DDT {d.numero_completo} non è in stato confermato (stato: {d.stato})"})

    doc_date_str = data.get('data_documento')
    doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()
    anno = doc_date.year
    numero = get_next_invoice_number(anno, db)
    numero_completo = f"FT-{anno}-{numero:04d}"

    condizioni = data.get('condizioni_pagamento', cliente.condizioni_pagamento or '30gg fm')

    totale_imponibile = 0.0
    totale_imposta = 0.0
    castelletto = {}
    invoice_items = []

    for ddt in ddts:
        for item in ddt.items:
            imp_riga = round(item.quantita * item.prezzo_unitario, 2)
            iva_riga = round(imp_riga * (item.aliquota_iva / 100.0), 2)
            totale_imponibile += imp_riga
            totale_imposta += iva_riga

            aliquota_key = str(item.aliquota_iva)
            if aliquota_key not in castelletto:
                castelletto[aliquota_key] = {"imponibile": 0.0, "imposta": 0.0}
            castelletto[aliquota_key]["imponibile"] = round(castelletto[aliquota_key]["imponibile"] + imp_riga, 2)
            castelletto[aliquota_key]["imposta"] = round(castelletto[aliquota_key]["imposta"] + iva_riga, 2)

            inv_item = InvoiceItem(
                delivery_note_id=ddt.id,
                product_id=item.product_id,
                descrizione=item.descrizione,
                unita_misura=item.unita_misura,
                colli=item.colli,
                quantita=item.quantita,
                prezzo_unitario=item.prezzo_unitario,
                aliquota_iva=item.aliquota_iva,
                imponibile_riga=imp_riga,
                lotto=item.lotto,
                data_scadenza=item.data_scadenza
            )
            invoice_items.append(inv_item)

    totale_imponibile = round(totale_imponibile, 2)
    totale_imposta = round(totale_imposta, 2)
    totale_fattura = round(totale_imponibile + totale_imposta, 2)

    rate_data = calculate_installments(totale_fattura, doc_date, condizioni)
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
        tipo_documento='TD24',
        data_documento=doc_date,
        cliente_id=cliente.id,
        condizioni_pagamento=condizioni,
        esigibilita_iva=data.get('esigibilita_iva', 'I'),
        totale_imponibile=totale_imponibile,
        totale_imposta=totale_imposta,
        totale_fattura=totale_fattura,
        castelletto_iva=castelletto,
        stato='emessa',
        note=data.get('note'),
        items=invoice_items,
        installments=installments
    )
    db.add(invoice)

    for ddt in ddts:
        ddt.stato = 'fatturato'

    db.flush()
    je = auto_post_invoice_to_accounting(invoice, db)
    try:
        dispatch_event(
            event_type_code="EMISSIONE_FATTURA",
            titolo=f"Fattura {invoice.numero_completo}",
            descrizione=f"Emessa fattura differita {invoice.numero_completo} - Totale {invoice.totale_fattura:.2f} €",
            entita_tipo="invoice",
            entita_id=invoice.id,
            partner_id=invoice.cliente_id,
            payload_dati={"totale": float(invoice.totale_fattura), "journal_entry_id": je.id if je else None},
            db=db
        )
    except Exception:
        pass

    try:
        db.commit()
        db.refresh(invoice)
        return invoice
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice_direct(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    cliente_id = data.get('cliente_id')
    if not cliente_id:
        return JSONResponse(status_code=400, content={"error": "cliente_id is required"})

    cliente = db.get(Partner, cliente_id)
    if not cliente:
        return JSONResponse(status_code=404, content={"error": "Cliente non trovato"})

    items_data = data.get('items', [])
    if not items_data:
        return JSONResponse(status_code=400, content={"error": "At least one item is required"})

    doc_date_str = data.get('data_documento')
    doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()
    anno = doc_date.year
    numero = get_next_invoice_number(anno, db)
    numero_completo = f"FT-{anno}-{numero:04d}"

    condizioni = data.get('condizioni_pagamento', cliente.condizioni_pagamento or '30gg fm')

    totale_imponibile = 0.0
    totale_imposta = 0.0
    castelletto = {}
    invoice_items = []

    for item in items_data:
        prod_id = item.get('product_id')
        product = db.get(Product, prod_id) if prod_id else None
        descrizione = item.get('descrizione', product.descrizione if product else 'Articolo')
        unita_misura = item.get('unita_misura', product.unita_misura if product else 'KG')
        colli = int(item.get('colli', 1))
        quantita = float(item.get('quantita', 1.0))
        prezzo_unitario = float(item.get('prezzo_unitario', product.prezzo_vendita if product else 0.0))
        aliquota_iva = int(item.get('aliquota_iva', product.aliquota_iva if product else 4))

        imp_riga = round(quantita * prezzo_unitario, 2)
        iva_riga = round(imp_riga * (aliquota_iva / 100.0), 2)
        totale_imponibile += imp_riga
        totale_imposta += iva_riga

        aliquota_key = str(aliquota_iva)
        if aliquota_key not in castelletto:
            castelletto[aliquota_key] = {"imponibile": 0.0, "imposta": 0.0}
        castelletto[aliquota_key]["imponibile"] = round(castelletto[aliquota_key]["imponibile"] + imp_riga, 2)
        castelletto[aliquota_key]["imposta"] = round(castelletto[aliquota_key]["imposta"] + iva_riga, 2)

        inv_item = InvoiceItem(
            product_id=prod_id,
            descrizione=descrizione,
            unita_misura=unita_misura,
            colli=colli,
            quantita=quantita,
            prezzo_unitario=prezzo_unitario,
            aliquota_iva=aliquota_iva,
            imponibile_riga=imp_riga,
            lotto=item.get('lotto'),
            data_scadenza=datetime.strptime(item.get('data_scadenza'), '%Y-%m-%d').date() if item.get('data_scadenza') else None
        )
        invoice_items.append(inv_item)

    totale_imponibile = round(totale_imponibile, 2)
    totale_imposta = round(totale_imposta, 2)
    totale_fattura = round(totale_imponibile + totale_imposta, 2)

    rate_data = calculate_installments(totale_fattura, doc_date, condizioni)
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
        data_documento=doc_date,
        cliente_id=cliente.id,
        condizioni_pagamento=condizioni,
        esigibilita_iva=data.get('esigibilita_iva', 'I'),
        totale_imponibile=totale_imponibile,
        totale_imposta=totale_imposta,
        totale_fattura=totale_fattura,
        castelletto_iva=castelletto,
        stato='emessa',
        note=data.get('note'),
        items=invoice_items,
        installments=installments
    )
    db.add(invoice)
    db.flush()
    je = auto_post_invoice_to_accounting(invoice, db)
    try:
        dispatch_event(
            event_type_code="EMISSIONE_FATTURA",
            titolo=f"Fattura {invoice.numero_completo}",
            descrizione=f"Emessa fattura {invoice.numero_completo} ({invoice.tipo_documento}) - Totale {invoice.totale_fattura:.2f} €",
            entita_tipo="invoice",
            entita_id=invoice.id,
            partner_id=invoice.cliente_id,
            payload_dati={"totale": float(invoice.totale_fattura), "journal_entry_id": je.id if je else None},
            db=db
        )
    except Exception:
        pass

    try:
        db.commit()
        db.refresh(invoice)
        return invoice
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/invoices/{iid}/credit-note", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_credit_note_from_invoice(
    iid: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    inv = db.get(Invoice, iid)
    if not inv:
        return JSONResponse(status_code=404, content={"error": "Fattura d'origine non trovata"})
    if inv.tipo_documento == 'TD04':
        return JSONResponse(status_code=400, content={"error": "Impossibile emettere una nota di credito a storno di un'altra nota di credito"})

    data = await request.json()
    items_to_reverse = data.get('items', [])
    if not items_to_reverse:
        return JSONResponse(status_code=400, content={"error": "Almeno una riga da stornare richiesta"})

    today = date.today()
    anno = today.year
    numero = get_next_credit_note_number(anno, db)
    numero_completo = f"NC-{anno}-{numero:04d}"

    causale = data.get('causale_storno') or f"Storno parziale su fattura {inv.numero_completo}"
    compensa_scadenzario = data.get('compensa_scadenzario', True)
    reintegro_magazzino = data.get('reintegro_magazzino', False)

    items_map = {it.id: it for it in inv.items}
    nc_items = []
    castelletto = {}
    totale_imponibile = 0.0
    totale_imposta = 0.0

    for it_rev in items_to_reverse:
        orig_item_id = it_rev.get('invoice_item_id')
        orig_item = items_map.get(orig_item_id)
        if not orig_item:
            return JSONResponse(status_code=400, content={"error": f"Riga fattura {orig_item_id} non trovata"})

        qta_storno = float(it_rev.get('quantita_stornata', orig_item.quantita))
        if qta_storno <= 0 or qta_storno > orig_item.quantita:
            return JSONResponse(status_code=400, content={"error": f"Quantità da stornare non valida ({qta_storno})"})

        prezzo_unit = float(orig_item.prezzo_unitario)
        aliq = int(orig_item.aliquota_iva or 0)
        imp_riga = round(qta_storno * prezzo_unit, 2)
        imposta_riga = round(imp_riga * (aliq / 100.0), 2)

        totale_imponibile += imp_riga
        totale_imposta += imposta_riga

        aliq_key = str(aliq)
        if aliq_key not in castelletto:
            castelletto[aliq_key] = {"imponibile": 0.0, "imposta": 0.0}
        castelletto[aliq_key]["imponibile"] += imp_riga
        castelletto[aliq_key]["imposta"] += imposta_riga

        nc_items.append(InvoiceItem(
            product_id=orig_item.product_id,
            delivery_note_id=orig_item.delivery_note_id,
            descrizione=f"Storno: {orig_item.descrizione}",
            unita_misura=orig_item.unita_misura,
            colli=int(orig_item.colli or 1),
            quantita=qta_storno,
            prezzo_unitario=prezzo_unit,
            aliquota_iva=aliq,
            imponibile_riga=imp_riga,
            lotto=orig_item.lotto,
            data_scadenza=orig_item.data_scadenza
        ))

        if reintegro_magazzino and orig_item.lotto:
            p_reso = PurchaseDeliveryNote(
                numero_documento_fornitore=f"RESO-{numero_completo}",
                fornitore_id=inv.cliente_id,
                data_ricezione=today,
                note=f"Reso merci da cliente con Nota di Credito {numero_completo} (storno {inv.numero_completo})",
                items=[PurchaseDeliveryNoteItem(
                    product_id=orig_item.product_id,
                    descrizione=f"Reso: {orig_item.descrizione}",
                    colli=1,
                    quantita=qta_storno,
                    prezzo_unitario=prezzo_unit,
                    aliquota_iva=aliq,
                    lotto=orig_item.lotto,
                    data_scadenza=orig_item.data_scadenza or today
                )]
            )
            db.add(p_reso)

    totale_imponibile = round(totale_imponibile, 2)
    totale_imposta = round(totale_imposta, 2)
    totale_nc = round(totale_imponibile + totale_imposta, 2)

    for k in castelletto:
        castelletto[k]["imponibile"] = round(castelletto[k]["imponibile"], 2)
        castelletto[k]["imposta"] = round(castelletto[k]["imposta"], 2)

    nc = Invoice(
        numero=numero,
        anno=anno,
        numero_completo=numero_completo,
        tipo_documento='TD04',
        data_documento=today,
        cliente_id=inv.cliente_id,
        condizioni_pagamento=inv.condizioni_pagamento,
        esigibilita_iva=inv.esigibilita_iva,
        totale_imponibile=totale_imponibile,
        totale_imposta=totale_imposta,
        totale_fattura=totale_nc,
        castelletto_iva=castelletto,
        stato='emessa',
        note=causale,
        invoice_origine_id=inv.id,
        invoice_origine_numero=inv.numero_completo,
        causale_storno=causale,
        reintegro_magazzino=reintegro_magazzino,
        items=nc_items
    )
    db.add(nc)

    if compensa_scadenzario and inv.installments:
        residuo_storno = totale_nc
        sorted_installments = sorted(inv.installments, key=lambda x: x.data_scadenza)
        for inst in sorted_installments:
            if inst.stato == 'aperta' and residuo_storno > 0:
                if inst.importo <= residuo_storno:
                    residuo_storno = round(residuo_storno - inst.importo, 2)
                    inst.importo = 0.0
                    inst.stato = 'incassata'
                else:
                    inst.importo = round(inst.importo - residuo_storno, 2)
                    residuo_storno = 0.0

        if all(inst.stato == 'incassata' or inst.importo <= 0.0 for inst in inv.installments):
            inv.stato = 'saldata'

    db.flush()
    seed_default_accounting_causals(db)
    causal_nc = db.query(AccountingCausal).filter_by(codice="VEND_NC", attivo=True).first()
    je_nc = None
    if causal_nc and causal_nc.conto_dare_id and causal_nc.conto_avere_id and causal_nc.conto_iva_id:
        anno_c = date.today().year
        num_c = get_next_journal_entry_number(anno_c, db)
        num_comp_c = f"PN-{anno_c}-{num_c:04d}"
        tot_lordo_c = float(nc.totale_fattura)
        tot_iva_c = float(nc.totale_imposta or 0.0)
        tot_imp_c = round(tot_lordo_c - tot_iva_c, 2)
        cli_nome = inv.cliente.ragione_sociale if inv.cliente else "Cliente"

        je_nc = JournalEntry(
            numero=num_c,
            anno=anno_c,
            numero_completo=num_comp_c,
            data_registrazione=date.today(),
            data_competenza=date.today(),
            causale=f"Nota di Credito {nc.numero_completo} su {inv.numero_completo} a {cli_nome}",
            causale_id=causal_nc.id,
            totale_dare=tot_lordo_c,
            totale_avere=tot_lordo_c,
            stato="confermata"
        )
        db.add(je_nc)
        db.flush()

        db.add(JournalItem(
            journal_entry_id=je_nc.id,
            account_id=causal_nc.conto_dare_id,
            descrizione_riga=f"Storno ricavi {nc.numero_completo}",
            dare=tot_imp_c,
            avere=0.0
        ))
        db.add(JournalItem(
            journal_entry_id=je_nc.id,
            account_id=causal_nc.conto_iva_id,
            descrizione_riga=f"Storno IVA a debito {nc.numero_completo}",
            dare=tot_iva_c,
            avere=0.0
        ))
        db.add(JournalItem(
            journal_entry_id=je_nc.id,
            account_id=causal_nc.conto_avere_id,
            partner_id=nc.cliente_id,
            descrizione_riga=f"Storno credito cliente {nc.numero_completo}",
            dare=0.0,
            avere=tot_lordo_c
        ))

    try:
        dispatch_event(
            event_type_code="EMISSIONE_FATTURA",
            azione="emissione_nota_credito",
            titolo=f"Nota di Credito {nc.numero_completo}",
            descrizione=f"Emessa nota di credito {nc.numero_completo} a storno di {inv.numero_completo} ({nc.totale_fattura:.2f} €)",
            entita_tipo="invoice",
            entita_id=nc.id,
            partner_id=nc.cliente_id,
            payload_dati={"totale": float(nc.totale_fattura), "journal_entry_id": je_nc.id if je_nc else None},
            db=db
        )
    except Exception:
        pass

    try:
        db.commit()
        db.refresh(nc)
        return nc
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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
    inst = db.get(InvoiceInstallment, inst_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Installment not found")

    inst.stato = 'incassata'
    inst.data_incasso = date.today()

    invoice = inst.invoice
    if all(i.stato == 'incassata' for i in invoice.installments):
        invoice.stato = 'saldata'

    db.flush()
    seed_default_accounting_causals(db)
    causal_inc = db.query(AccountingCausal).filter_by(codice="INCASSO_RATA", attivo=True).first()
    je_inc = None
    if causal_inc and causal_inc.conto_dare_id and causal_inc.conto_avere_id:
        anno_c = date.today().year
        num_c = get_next_journal_entry_number(anno_c, db)
        num_comp_c = f"PN-{anno_c}-{num_c:04d}"
        importo_inc = float(inst.importo)
        cli_nome = invoice.cliente.ragione_sociale if invoice.cliente else "Cliente"

        je_inc = JournalEntry(
            numero=num_c,
            anno=anno_c,
            numero_completo=num_comp_c,
            data_registrazione=date.today(),
            data_competenza=date.today(),
            causale=f"Incasso rata {inst.numero_rata}/{inst.totale_rate} fattura {invoice.numero_completo} da {cli_nome}",
            causale_id=causal_inc.id,
            totale_dare=importo_inc,
            totale_avere=importo_inc,
            stato="confermata"
        )
        db.add(je_inc)
        db.flush()

        db.add(JournalItem(
            journal_entry_id=je_inc.id,
            account_id=causal_inc.conto_dare_id,
            descrizione_riga=f"Incasso banca rata {inst.numero_rata} FT {invoice.numero_completo}",
            dare=importo_inc,
            avere=0.0
        ))
        db.add(JournalItem(
            journal_entry_id=je_inc.id,
            account_id=causal_inc.conto_avere_id,
            partner_id=invoice.cliente_id,
            descrizione_riga=f"Chiusura credito rata {inst.numero_rata} FT {invoice.numero_completo}",
            dare=0.0,
            avere=importo_inc
        ))

    try:
        dispatch_event(
            db=db,
            event_type_code="INCASSO_RATA",
            azione="incasso_rata",
            titolo=f"Incasso Rata FT {invoice.numero_completo}",
            descrizione=f"Incassata rata {inst.numero_rata}/{inst.totale_rate} per {invoice.numero_completo} ({inst.importo:.2f} €)",
            entita_tipo="installment",
            entita_id=inst.id,
            partner_id=invoice.cliente_id,
            payload_dati={"importo": float(inst.importo), "journal_entry_id": je_inc.id if je_inc else None}
        )
    except Exception:
        pass

    try:
        db.commit()
        db.refresh(inst)
        return inst
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
