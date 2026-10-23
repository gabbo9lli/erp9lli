from typing import Optional, List
from datetime import date
from pydantic import BaseModel, ConfigDict
from schemas.partner import PartnerResponse
from schemas.product import ProductResponse

class DeliveryNoteItemBase(BaseModel):
    product_id: Optional[int] = None
    descrizione: str
    unita_misura: str = "KG"
    colli: int = 1
    quantita: float = 1.0
    prezzo_unitario: float = 0.0
    aliquota_iva: int = 4
    lotto: Optional[str] = None
    data_scadenza: Optional[date] = None

class DeliveryNoteItemResponse(DeliveryNoteItemBase):
    id: int
    product: Optional[ProductResponse] = None

    model_config = ConfigDict(from_attributes=True)

class DeliveryNoteBase(BaseModel):
    data_documento: date
    cliente_id: int
    vettore_id: Optional[int] = None
    causale_trasporto: str = "Vendita"
    porto: str = "Franco"
    aspetto_beni: str = "Colli"
    note: Optional[str] = None

class DeliveryNoteResponse(DeliveryNoteBase):
    id: int
    numero: int
    anno: int
    numero_completo: str
    colli_totali: int
    peso_totale_netto: float
    peso_totale_lordo: float
    totale_imponibile: float
    stato: str
    cliente: Optional[PartnerResponse] = None
    vettore: Optional[PartnerResponse] = None
    items: List[DeliveryNoteItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
