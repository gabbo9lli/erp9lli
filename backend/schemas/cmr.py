from typing import Optional, List
from datetime import date
from pydantic import BaseModel, ConfigDict
from schemas.partner import PartnerResponse

class CmrItemResponse(BaseModel):
    id: int
    riga_numero: int
    contrassegno_lotto: Optional[str] = None
    numero_colli: int = 1
    modo_imballaggio: str = "Casse su Pallet"
    natura_merce: str = "Ortofrutta Bio"
    codice_nc: Optional[str] = None
    peso_netto_kg: float = 0.0
    peso_lordo_kg: float = 0.0

    model_config = ConfigDict(from_attributes=True)

class CmrDocumentBase(BaseModel):
    data_documento: date
    cliente_id: int
    vettore_id: Optional[int] = None
    delivery_note_id: Optional[int] = None
    luogo_carico: str = "SEDE MITTENTE"
    luogo_consegna: str
    targa_automezzo: Optional[str] = None
    targa_rimorchio: Optional[str] = None
    istruzioni_mittente: Optional[str] = None

class CmrDocumentResponse(CmrDocumentBase):
    id: int
    numero: int
    anno: int
    numero_completo: str
    totale_colli: int
    peso_totale_netto: float
    peso_totale_lordo: float
    ha_allegato_righe: bool = False
    stato: str
    cliente: Optional[PartnerResponse] = None
    vettore: Optional[PartnerResponse] = None
    items: List[CmrItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
