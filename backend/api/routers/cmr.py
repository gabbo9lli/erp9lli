from typing import Optional, List
from datetime import datetime, date
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import CmrDocument, CmrItem, DeliveryNote, Partner, Product, User
from api.deps import require_auth

router = APIRouter(prefix="/api/cmr", tags=["CMR Export"])

def get_next_cmr_number(anno: int, db: Session) -> int:
    max_num = db.query(func.max(CmrDocument.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

@router.get("")
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
    return [d.to_dict() for d in documents]

@router.get("/{cid}")
def get_cmr_detail(
    cid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    cmr = db.get(CmrDocument, cid)
    if not cmr:
        return JSONResponse(status_code=404, content={"error": "CMR not found"})
    return cmr.to_dict()

@router.post("/from-ddt/{ddt_id}", status_code=status.HTTP_201_CREATED)
def create_cmr_from_ddt(
    ddt_id: int,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    ddt = db.get(DeliveryNote, ddt_id)
    if not ddt:
        return JSONResponse(status_code=404, content={"error": "DDT not found"})
    if not ddt.cliente:
        return JSONResponse(status_code=400, content={"error": "DDT privo di cliente associato"})

    today = date.today()
    anno = today.year
    numero = get_next_cmr_number(anno, db)
    numero_completo = f"CMR-{anno}-{numero:04d}"

    vettore_nome = (ddt.vettore.ragione_sociale if ddt.vettore else "").upper()
    if "LD TRASPORTI" in vettore_nome:
        luogo_carico = "ALESSANDRIA (AL)"
    else:
        luogo_carico = "SEDE MITTENTE (BOLOGNA)"

    luogo_consegna_parts = [
        ddt.cliente.indirizzo or "",
        ddt.cliente.citta or "",
        f"({ddt.cliente.nazione})" if ddt.cliente.nazione else ""
    ]
    luogo_consegna = ", ".join([p for p in luogo_consegna_parts if p]) or "DESTINAZIONE CLIENTE"

    cmr_items = []
    totale_colli = 0
    peso_totale_netto = 0.0
    peso_totale_lordo = 0.0

    for idx, d_item in enumerate(ddt.items):
        colli = d_item.colli or 1
        p_netto = float(d_item.quantita or 0.0)
        p_lordo = round(p_netto * 1.05, 2)

        totale_colli += colli
        peso_totale_netto += p_netto
        peso_totale_lordo += p_lordo

        codice_nc = d_item.product.codice_nc if (d_item.product and hasattr(d_item.product, 'codice_nc')) else None

        cmr_items.append(CmrItem(
            riga_numero=idx + 1,
            contrassegno_lotto=d_item.lotto,
            numero_colli=colli,
            modo_imballaggio="Casse su Pallet",
            natura_merce=d_item.descrizione,
            codice_nc=codice_nc,
            peso_netto_kg=p_netto,
            peso_lordo_kg=p_lordo
        ))

    ha_allegato_righe = len(cmr_items) > 21

    cmr = CmrDocument(
        numero=numero,
        anno=anno,
        numero_completo=numero_completo,
        data_documento=today,
        delivery_note_id=ddt.id,
        cliente_id=ddt.cliente_id,
        vettore_id=ddt.vettore_id,
        luogo_carico=luogo_carico,
        luogo_consegna=luogo_consegna,
        targa_automezzo=None,
        targa_rimorchio=None,
        istruzioni_mittente="Merci biologiche destinate all'export comunitario. Origine preferenziale CE.",
        totale_colli=totale_colli,
        peso_totale_netto=round(peso_totale_netto, 2),
        peso_totale_lordo=round(peso_totale_lordo, 2),
        ha_allegato_righe=ha_allegato_righe,
        stato="emesso",
        items=cmr_items
    )
    db.add(cmr)
    try:
        db.commit()
        db.refresh(cmr)
        return JSONResponse(status_code=201, content=cmr.to_dict())
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"error": str(e)})

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_cmr_manual(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    cliente_id = data.get('cliente_id')
    if not cliente_id:
        return JSONResponse(status_code=400, content={"error": "cliente_id obbligatorio"})
    cliente = db.get(Partner, cliente_id)
    if not cliente:
        return JSONResponse(status_code=404, content={"error": "Cliente non trovato"})

    items_data = data.get('items', [])
    if not items_data:
        return JSONResponse(status_code=400, content={"error": "Almeno una riga merce richiesta"})

    today = date.today()
    anno = today.year
    numero = get_next_cmr_number(anno, db)
    numero_completo = f"CMR-{anno}-{numero:04d}"

    vettore_id = data.get('vettore_id')
    vettore = db.get(Partner, vettore_id) if vettore_id else None
    vettore_nome = (vettore.ragione_sociale if vettore else "").upper()

    default_hub = "ALESSANDRIA (AL)" if "LD TRASPORTI" in vettore_nome else "SEDE MITTENTE"
    luogo_carico = data.get('luogo_carico') or default_hub

    totale_colli = 0
    peso_totale_netto = 0.0
    peso_totale_lordo = 0.0
    cmr_items = []

    for idx, it in enumerate(items_data):
        colli = int(it.get('numero_colli', 1))
        p_netto = float(it.get('peso_netto_kg', 0.0))
        p_lordo = float(it.get('peso_lordo_kg', p_netto * 1.05))

        totale_colli += colli
        peso_totale_netto += p_netto
        peso_totale_lordo += p_lordo

        cmr_items.append(CmrItem(
            riga_numero=idx + 1,
            contrassegno_lotto=it.get('contrassegno_lotto'),
            numero_colli=colli,
            modo_imballaggio=it.get('modo_imballaggio', 'Casse su Pallet'),
            natura_merce=it.get('natura_merce', 'Ortofrutta Bio'),
            codice_nc=it.get('codice_nc'),
            peso_netto_kg=round(p_netto, 2),
            peso_lordo_kg=round(p_lordo, 2)
        ))

    ha_allegato_righe = len(cmr_items) > 21

    cmr = CmrDocument(
        numero=numero,
        anno=anno,
        numero_completo=numero_completo,
        data_documento=today,
        delivery_note_id=data.get('delivery_note_id'),
        cliente_id=cliente.id,
        vettore_id=vettore_id,
        luogo_carico=luogo_carico,
        luogo_consegna=data.get('luogo_consegna') or f"{cliente.citta} ({cliente.nazione})",
        targa_automezzo=data.get('targa_automezzo'),
        targa_rimorchio=data.get('targa_rimorchio'),
        istruzioni_mittente=data.get('istruzioni_mittente', "Merci da agricoltura biologica. Origine preferenziale CE."),
        totale_colli=totale_colli,
        peso_totale_netto=round(peso_totale_netto, 2),
        peso_totale_lordo=round(peso_totale_lordo, 2),
        ha_allegato_righe=ha_allegato_righe,
        stato="emesso",
        items=cmr_items
    )
    db.add(cmr)
    try:
        db.commit()
        db.refresh(cmr)
        return JSONResponse(status_code=201, content=cmr.to_dict())
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"error": str(e)})

@router.put("/{cid}")
async def update_cmr(
    cid: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    cmr = db.get(CmrDocument, cid)
    if not cmr:
        return JSONResponse(status_code=404, content={"error": "CMR not found"})
    data = await request.json()
    if 'targa_automezzo' in data:
        cmr.targa_automezzo = data['targa_automezzo']
    if 'targa_rimorchio' in data:
        cmr.targa_rimorchio = data['targa_rimorchio']
    if 'luogo_carico' in data:
        cmr.luogo_carico = data['luogo_carico']
    if 'luogo_consegna' in data:
        cmr.luogo_consegna = data['luogo_consegna']
    if 'istruzioni_mittente' in data:
        cmr.istruzioni_mittente = data['istruzioni_mittente']
    try:
        db.commit()
        db.refresh(cmr)
        return cmr.to_dict()
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"error": str(e)})

@router.get("/{cid}/print")
def get_cmr_print_format(
    cid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    cmr = db.get(CmrDocument, cid)
    if not cmr:
        return JSONResponse(status_code=404, content={"error": "CMR not found"})

    boxes = {
        "numero_cmr": cmr.numero_completo,
        "data_emissione": cmr.data_documento.isoformat(),
        "casella_1_mittente": {
            "ragione_sociale": "ReteBio Società Cooperativa Agricola",
            "indirizzo": "Via della Cooperazione 12",
            "citta": "Bologna",
            "cap": "40100",
            "nazione": "IT",
            "piva": "IT01234567890"
        },
        "casella_2_destinatario": cmr.cliente.to_dict() if cmr.cliente else {},
        "casella_3_luogo_consegna": cmr.luogo_consegna,
        "casella_4_luogo_carico": {
            "luogo": cmr.luogo_carico,
            "data": cmr.data_documento.isoformat()
        },
        "casella_6_a_12_merci": [it.to_dict() for it in cmr.items] if not cmr.ha_allegato_righe else [{"dicitura": "--- VEDI ELENCO MERCE IN ALLEGATO ---"}],
        "caselle_merci": [it.to_dict() for it in cmr.items],
        "casella_13_istruzioni_mittente": cmr.istruzioni_mittente,
        "casella_16_trasportatore": {
            "ragione_sociale": cmr.vettore.ragione_sociale if cmr.vettore else "Vettore Incaricato",
            "indirizzo": cmr.vettore.indirizzo if cmr.vettore else "",
            "citta": cmr.vettore.citta if cmr.vettore else "",
            "targa_automezzo": cmr.targa_automezzo,
            "targa_rimorchio": cmr.targa_rimorchio
        },
        "totale_colli": cmr.totale_colli,
        "peso_totale_netto": cmr.peso_totale_netto,
        "peso_totale_lordo": cmr.peso_totale_lordo,
        "ha_allegato_righe": cmr.ha_allegato_righe
    }
    return boxes
