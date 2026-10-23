from typing import Optional, List
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from models import EventChannel, EventCategory, EventType, SystemEvent, User
from api.deps import require_auth
from services.event_dispatcher import (
    seed_default_channels_and_categories,
    dispatch_event,
    get_redis_connection
)
from rq import Queue
from schemas.event import EventChannelResponse, EventCategoryResponse, EventTypeResponse, SystemEventResponse

router = APIRouter(prefix="/api/events", tags=["Event Bus"])

@router.get("/channels", response_model=List[EventChannelResponse])
def get_event_channels(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    seed_default_channels_and_categories(db)
    channels = db.query(EventChannel).filter_by(attivo=True).order_by(EventChannel.codice.asc()).all()
    return channels

@router.post("/channels", response_model=EventChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_event_channel(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    codice = (data.get('codice') or '').strip().upper()
    nome = (data.get('nome') or '').strip()
    if not codice or not nome:
        raise HTTPException(status_code=400, detail="codice e nome obbligatori")
    ch = EventChannel(
        codice=codice,
        nome=nome,
        descrizione=data.get('descrizione'),
        tipo_dispatcher=data.get('tipo_dispatcher', 'internal'),
        configurazione=data.get('configurazione'),
        richiede_destinatario=data.get('richiede_destinatario', False),
        attivo=data.get('attivo', True)
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch

@router.get("/categories", response_model=List[EventCategoryResponse])
def get_event_categories(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    seed_default_channels_and_categories(db)
    categories = db.query(EventCategory).filter_by(attivo=True).order_by(EventCategory.codice.asc()).all()
    return categories

@router.get("/types", response_model=List[EventTypeResponse])
def get_event_types(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    seed_default_channels_and_categories(db)
    types = db.query(EventType).order_by(EventType.codice.asc()).all()
    return types

@router.post("/types", response_model=EventTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_event_type(
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    data = await request.json()
    codice = (data.get('codice') or '').strip().upper()
    nome = (data.get('nome') or '').strip()
    channel_id = data.get('channel_id')
    if not codice or not nome or not channel_id:
        raise HTTPException(status_code=400, detail="codice, nome e channel_id sono obbligatori")
    et = EventType(
        codice=codice,
        nome=nome,
        descrizione=data.get('descrizione'),
        channel_id=channel_id,
        category_id=data.get('category_id'),
        modalita_esecuzione=data.get('modalita_esecuzione', 'sincrono'),
        coda_nome=data.get('coda_nome', 'default'),
        livello_default=data.get('livello_default', 'info'),
        attivo=data.get('attivo', True)
    )
    db.add(et)
    db.commit()
    db.refresh(et)
    return et

@router.put("/types/{tid}", response_model=EventTypeResponse)
async def update_event_type_policy(
    tid: int,
    request: Request,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    et = db.get(EventType, tid)
    if not et:
        raise HTTPException(status_code=404, detail="Tipo evento non trovato")
    data = await request.json()
    if 'modalita_esecuzione' in data:
        if data['modalita_esecuzione'] not in ['sincrono', 'asincrono']:
            raise HTTPException(status_code=400, detail="modalita_esecuzione non valida (ammessi: sincrono, asincrono)")
        et.modalita_esecuzione = data['modalita_esecuzione']
    if 'coda_nome' in data:
        if data['coda_nome'] not in ['critical', 'emails', 'batch', 'default']:
            raise HTTPException(status_code=400, detail="coda_nome non valida (ammessi: critical, emails, batch, default)")
        et.coda_nome = data['coda_nome']
    if 'channel_id' in data:
        et.channel_id = data['channel_id']
    if 'category_id' in data:
        et.category_id = data['category_id']
    if 'attivo' in data:
        et.attivo = data['attivo']
    db.commit()
    db.refresh(et)
    return et

@router.get("/queues")
def get_redis_queues_stats(
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    queue_names = ['critical', 'emails', 'batch', 'default']
    queues_stats = []
    redis_conn = get_redis_connection()

    for q_name in queue_names:
        job_count = 0
        if redis_conn:
            try:
                q = Queue(q_name, connection=redis_conn)
                job_count = len(q)
            except Exception:
                pass
        queues_stats.append({
            "name": q_name,
            "count": job_count,
            "active": redis_conn is not None
        })
    return {"queues": queues_stats}

@router.get("", response_model=List[SystemEventResponse])
def get_events(
    channel: Optional[str] = None,
    stato: Optional[str] = None,
    search: Optional[str] = None,
    is_async: Optional[bool] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    seed_default_channels_and_categories(db)
    query = db.query(SystemEvent)
    if channel and channel != 'tutti':
        query = query.join(SystemEvent.channel).filter(EventChannel.codice == channel)
    if stato and stato != 'tutti':
        query = query.filter(SystemEvent.stato == stato)
    if search:
        search_f = f"%{search}%"
        query = query.filter((SystemEvent.titolo.ilike(search_f)) | (SystemEvent.azione.ilike(search_f)) | (SystemEvent.descrizione.ilike(search_f)))
    if is_async is not None:
        query = query.filter(SystemEvent.is_async == is_async)

    events = query.order_by(SystemEvent.data_creazione.desc()).limit(100).all()
    return events

@router.get("/{eid}", response_model=SystemEventResponse)
def get_event_detail(
    eid: int,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    ev = db.get(SystemEvent, eid)
    if not ev:
        raise HTTPException(status_code=404, detail="Evento non trovato")
    return ev

@router.post("", response_model=SystemEventResponse)
async def create_event_endpoint(
    request: Request,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    data = await request.json()
    is_async = data.get('is_async', False)
    ev = dispatch_event(
        channel_code=data.get('channel_code', 'AUDIT'),
        category_code=data.get('category_code', 'SISTEMA'),
        azione=data.get('azione', 'custom_event'),
        titolo=data.get('titolo', 'Evento Utente'),
        descrizione=data.get('descrizione'),
        payload_dati=data.get('payload_dati'),
        destinatario_recapito=data.get('destinatario_recapito'),
        partner_id=data.get('partner_id'),
        entita_tipo=data.get('entita_tipo'),
        entita_id=data.get('entita_id'),
        is_async=is_async,
        livello=data.get('livello', 'info'),
        db=db
    )
    code = 202 if is_async else 201
    return JSONResponse(status_code=code, content=ev.to_dict())
