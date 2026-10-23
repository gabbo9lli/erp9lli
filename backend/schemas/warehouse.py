from typing import Optional, List
from datetime import date
from pydantic import BaseModel, ConfigDict
from schemas.partner import PartnerResponse
from schemas.product import ProductResponse

class PurchaseDeliveryNoteItemResponse(BaseModel):
    id: int
    product_id: int
    descrizione: str
    unita_misura: str = "KG"
    colli: int = 1
    quantita: float = 1.0
    prezzo_unitario: float = 0.0
    aliquota_iva: int = 4
    lotto: Optional[str] = None
    data_scadenza: Optional[date] = None
    product: Optional[ProductResponse] = None

    model_config = ConfigDict(from_attributes=True)

class PurchaseDeliveryNoteBase(BaseModel):
    numero_documento_fornitore: str
    data_documento: date
    data_ricezione: date
    fornitore_id: int
    note: Optional[str] = None

class PurchaseDeliveryNoteResponse(PurchaseDeliveryNoteBase):
    id: int
    colli_totali: int
    peso_totale_netto: float
    totale_imponibile: float
    fornitore: Optional[PartnerResponse] = None
    items: List[PurchaseDeliveryNoteItemResponse] = []

    model_config = ConfigDict(from_attributes=True)

class StockItemResponse(BaseModel):
    product_id: int
    product_codice: str
    product_descrizione: str
    lotto: Optional[str] = None
    data_scadenza: Optional[str] = None
    giorni_a_scadere: Optional[int] = None
    stato_scadenza: str
    giacenza_kg: float
    colli_disponibili: int

    model_config = ConfigDict(from_attributes=True)

class FefoSuggestionResponse(BaseModel):
    product_id: int
    lotto: Optional[str] = None
    data_scadenza: Optional[str] = None
    giacenza_kg: float
    colli_disponibili: int
    consigliato_fefo: bool

    model_config = ConfigDict(from_attributes=True)
