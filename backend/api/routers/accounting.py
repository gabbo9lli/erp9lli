import io
import csv
from typing import Optional, List
from datetime import datetime, date
from fastapi import APIRouter, Request, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import Account, JournalEntry, JournalItem, AccountingCausal, Partner, User
from api.deps import require_auth
from seed_accounting import seed_default_accounting_causals, seed_chart_of_accounts
from schemas.accounting import AccountResponse, AccountingCausalResponse, JournalEntryResponse
from services.accounting_service import AccountingService

router = APIRouter(prefix="/api/accounting", tags=["Accounting"])

def get_next_journal_entry_number(anno: int, db: Session) -> int:
    max_num = db.query(func.max(JournalEntry.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

@router.get("/accounts", response_model=List[AccountResponse])
def get_accounts(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    seed_chart_of_accounts(db)
    accounts = db.query(Account).order_by(Account.codice.asc()).all()
    return accounts

@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    codice = data.get('codice')
    nome = data.get('nome')
    tipo = data.get('tipo')
    if not codice or not nome or not tipo:
        raise HTTPException(status_code=400, detail="codice, nome e tipo sono obbligatori")
    if db.query(Account).filter_by(codice=codice).first():
        raise HTTPException(status_code=400, detail=f"Conto con codice {codice} già esistente")
    acc = Account(codice=codice, nome=nome, tipo=tipo, attivo=data.get('attivo', True))
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc

@router.get("/causals", response_model=List[AccountingCausalResponse])
def get_accounting_causals(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    seed_default_accounting_causals(db)
    causals = db.query(AccountingCausal).order_by(AccountingCausal.codice.asc()).all()
    return causals

@router.post("/causals", response_model=AccountingCausalResponse, status_code=status.HTTP_201_CREATED)
async def create_accounting_causal(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    codice = (data.get('codice') or '').strip().upper()
    descrizione = (data.get('descrizione') or '').strip()
    if not codice or not descrizione:
        raise HTTPException(status_code=400, detail="codice e descrizione sono obbligatori")
    if db.query(AccountingCausal).filter_by(codice=codice).first():
        raise HTTPException(status_code=400, detail=f"Causale {codice} già esistente")
    causal = AccountingCausal(
        codice=codice,
        descrizione=descrizione,
        tipo_registro=data.get('tipo_registro', 'generale'),
        conto_dare_id=data.get('conto_dare_id'),
        conto_avere_id=data.get('conto_avere_id'),
        conto_iva_id=data.get('conto_iva_id'),
        template_descrizione=data.get('template_descrizione'),
        attivo=data.get('attivo', True)
    )
    db.add(causal)
    db.commit()
    db.refresh(causal)
    return causal

@router.put("/causals/{cid}", response_model=AccountingCausalResponse)
async def update_accounting_causal(
    cid: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    causal = db.get(AccountingCausal, cid)
    if not causal:
        raise HTTPException(status_code=404, detail="Causale non trovata")
    data = await request.json()
    for field in ['descrizione', 'tipo_registro', 'conto_dare_id', 'conto_avere_id', 'conto_iva_id', 'template_descrizione', 'attivo']:
        if field in data:
            setattr(causal, field, data[field])
    db.commit()
    db.refresh(causal)
    return causal

@router.get("/entries", response_model=List[JournalEntryResponse])
def get_journal_entries(
    anno: Optional[int] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    query = db.query(JournalEntry)
    if anno:
        query = query.filter_by(anno=anno)
    if search:
        query = query.filter(JournalEntry.causale.ilike(f"%{search}%"))
    entries = query.order_by(JournalEntry.data_registrazione.desc(), JournalEntry.numero.desc()).all()
    return entries

@router.get("/entries/{eid}", response_model=JournalEntryResponse)
def get_journal_entry_detail(
    eid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    entry = db.get(JournalEntry, eid)
    if not entry:
        raise HTTPException(status_code=404, detail="Registrazione non trovata")
    return entry

@router.post("/entries", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    return AccountingService.create_journal_entry(db, data)

@router.get("/reports/libro-giornale")
def report_libro_giornale(
    anno: Optional[int] = None,
    format: Optional[str] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    query = db.query(JournalEntry).filter_by(stato='confermata')
    if anno:
        query = query.filter_by(anno=anno)
    entries = query.order_by(JournalEntry.data_registrazione.asc(), JournalEntry.numero.asc()).all()

    righe = []
    tot_dare = 0.0
    tot_avere = 0.0

    for entry in entries:
        for it in entry.items:
            tot_dare += it.dare
            tot_avere += it.avere
            righe.append({
                "entry_id": entry.id,
                "data": entry.data_registrazione.isoformat(),
                "numero": entry.numero_completo,
                "causale": entry.causale,
                "account_codice": it.account.codice if it.account else "",
                "account_nome": it.account.nome if it.account else "",
                "partner_nome": it.partner.ragione_sociale if it.partner else "",
                "dare": it.dare,
                "avere": it.avere
            })

    tot_dare = round(tot_dare, 2)
    tot_avere = round(tot_avere, 2)

    if format == 'csv':
        si = io.StringIO()
        cw = csv.writer(si, delimiter=';')
        cw.writerow(["Data", "Numero", "Causale", "Codice", "Conto", "Partner", "Dare", "Avere"])
        for r in righe:
            cw.writerow([r["data"], r["numero"], r["causale"], r["account_codice"], r["account_nome"], r["partner_nome"], f"{r['dare']:.2f}", f"{r['avere']:.2f}"])
        cw.writerow([])
        cw.writerow(["TOTALI", "", "", "", "", "", f"{tot_dare:.2f}", f"{tot_avere:.2f}"])
        output = si.getvalue()
        return Response(
            content=output,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=libro_giornale.csv"}
        )

    return {
        "anno": anno or date.today().year,
        "totale_dare": tot_dare,
        "totale_avere": tot_avere,
        "quadratura": round(tot_dare - tot_avere, 2) == 0.0,
        "righe": righe
    }

@router.get("/reports/mastro")
def report_mastro(
    account_id: int,
    partner_id: Optional[int] = None,
    format: Optional[str] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    account = db.get(Account, account_id)
    if not account:
        return JSONResponse(status_code=404, content={"error": "Account not found"})

    query = db.query(JournalItem).join(JournalEntry).filter(
        JournalItem.account_id == account.id,
        JournalEntry.stato == 'confermata'
    )
    if partner_id:
        query = query.filter(JournalItem.partner_id == partner_id)

    items = query.order_by(JournalEntry.data_registrazione.asc(), JournalEntry.numero.asc()).all()

    saldo_progressivo = 0.0
    movimenti = []
    tot_dare = 0.0
    tot_avere = 0.0

    for it in items:
        tot_dare += it.dare
        tot_avere += it.avere
        if account.tipo in ['attivo', 'costi']:
            saldo_progressivo += (it.dare - it.avere)
        else:
            saldo_progressivo += (it.avere - it.dare)

        movimenti.append({
            "id": it.id,
            "data": it.entry.data_registrazione.isoformat(),
            "numero": it.entry.numero_completo,
            "causale": it.entry.causale,
            "partner_nome": it.partner.ragione_sociale if it.partner else None,
            "dare": it.dare,
            "avere": it.avere,
            "saldo_progressivo": round(saldo_progressivo, 2)
        })

    tot_dare = round(tot_dare, 2)
    tot_avere = round(tot_avere, 2)
    saldo_finale = round(saldo_progressivo, 2)

    if format == 'csv':
        si = io.StringIO()
        cw = csv.writer(si, delimiter=';')
        cw.writerow(["Estratto Conto Mastro", f"{account.codice} - {account.nome} ({account.tipo})"])
        cw.writerow(["Data", "Numero", "Causale", "Partner", "Dare", "Avere", "Saldo Progressivo"])
        for m in movimenti:
            cw.writerow([m["data"], m["numero"], m["causale"], m["partner_nome"] or "", f"{m['dare']:.2f}", f"{m['avere']:.2f}", f"{m['saldo_progressivo']:.2f}"])
        cw.writerow([])
        cw.writerow(["TOTALI", "", "", "", f"{tot_dare:.2f}", f"{tot_avere:.2f}", f"SALDO FINALE: {saldo_finale:.2f}"])
        output = si.getvalue()
        return Response(
            content=output,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=mastro_{account.codice}.csv"}
        )

    return {
        "conto": account.to_dict(),
        "totale_dare": tot_dare,
        "totale_avere": tot_avere,
        "saldo_finale": saldo_finale,
        "movimenti": movimenti
    }

@router.get("/reports/bilancio-verifica")
def report_bilancio_verifica(
    anno: Optional[int] = None,
    format: Optional[str] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    accounts = db.query(Account).order_by(Account.codice.asc()).all()

    conti_report = []
    tot_dare_gen = 0.0
    tot_avere_gen = 0.0

    for acc in accounts:
        items_query = db.query(JournalItem).join(JournalEntry).filter(
            JournalItem.account_id == acc.id,
            JournalEntry.stato == 'confermata'
        )
        if anno:
            items_query = items_query.filter(JournalEntry.anno == anno)

        items = items_query.all()
        if not items:
            continue

        acc_dare = round(sum(it.dare for it in items), 2)
        acc_avere = round(sum(it.avere for it in items), 2)

        if acc.tipo in ['attivo', 'costi']:
            saldo_netto = round(acc_dare - acc_avere, 2)
        else:
            saldo_netto = round(acc_avere - acc_dare, 2)

        tot_dare_gen += acc_dare
        tot_avere_gen += acc_avere

        conti_report.append({
            "account_id": acc.id,
            "codice": acc.codice,
            "nome": acc.nome,
            "tipo": acc.tipo,
            "totale_dare": acc_dare,
            "totale_avere": acc_avere,
            "saldo_netto": saldo_netto
        })

    tot_dare_gen = round(tot_dare_gen, 2)
    tot_avere_gen = round(tot_avere_gen, 2)

    if format == 'csv':
        si = io.StringIO()
        cw = csv.writer(si, delimiter=';')
        cw.writerow(["Codice", "Conto", "Mastro", "Totale Dare", "Totale Avere", "Saldo Netto"])
        for c in conti_report:
            cw.writerow([c["codice"], c["nome"], c["tipo"], f"{c['totale_dare']:.2f}", f"{c['totale_avere']:.2f}", f"{c['saldo_netto']:.2f}"])
        cw.writerow([])
        cw.writerow(["TOTALI A PAREGGIO", "", "", f"{tot_dare_gen:.2f}", f"{tot_avere_gen:.2f}", ""])
        output = si.getvalue()
        return Response(
            content=output,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=bilancio_verifica.csv"}
        )

    return {
        "anno": anno or date.today().year,
        "totale_dare": tot_dare_gen,
        "totale_avere": tot_avere_gen,
        "quadratura": round(tot_dare_gen - tot_avere_gen, 2) == 0.0,
        "conti": conti_report
    }
