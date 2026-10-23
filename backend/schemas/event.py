from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class EventChannelResponse(BaseModel):
    id: int
    codice: str
    nome: str
    descrizione: Optional[str] = None
    tipo_dispatcher: str = "internal"
    richiede_destinatario: bool = False
    attivo: bool = True

    model_config = ConfigDict(from_attributes=True)

class EventCategoryResponse(BaseModel):
    id: int
    codice: str
    nome: str
    colore_badge: Optional[str] = None
    icona: Optional[str] = None
    attivo: bool = True

    model_config = ConfigDict(from_attributes=True)

class EventTypeResponse(BaseModel):
    id: int
    codice: str
    nome: str
    descrizione: Optional[str] = None
    channel_id: int
    category_id: Optional[int] = None
    modalita_esecuzione: str = "sincrono"
    coda_nome: str = "default"
    livello_default: str = "info"
    attivo: bool = True

    model_config = ConfigDict(from_attributes=True)

class SystemEventResponse(BaseModel):
    id: int
    channel_id: Optional[int] = None
    category_id: Optional[int] = None
    event_type_id: Optional[int] = None
    coda_nome: str = "default"
    livello: str = "info"
    azione: str
    titolo: str
    descrizione: Optional[str] = None
    payload_dati: Optional[Dict[str, Any]] = None
    is_async: bool = False
    progresso: int = 0
    stato: str
    note_esito: Optional[str] = None
    channel_codice: Optional[str] = None
    category_codice: Optional[str] = None
    channel: Optional[EventChannelResponse] = None
    category: Optional[EventCategoryResponse] = None
    event_type: Optional[EventTypeResponse] = None

    model_config = ConfigDict(from_attributes=True)
