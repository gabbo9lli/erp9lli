from typing import Optional, List
from datetime import date
from pydantic import BaseModel, ConfigDict
from schemas.partner import PartnerResponse
from schemas.product import ProductResponse

class OrderItemBase(BaseModel):
    product_id: Optional[int] = None
    sequenza: int = 5
    descrizione: str
    unita_misura: str = "KG"
    colli_ordinati: int = 1
    quantita_ordinata: float = 1.0
    prezzo_unitario: float = 0.0
    aliquota_iva: int = 4
    lotto: Optional[str] = None
    stato: str = "aperto"

class OrderItemResponse(OrderItemBase):
    id: int
    colli_consegnati: int = 0
    quantita_consegnata: float = 0.0
    quantita_residua: float
    colli_residui: int
    product: Optional[ProductResponse] = None

    model_config = ConfigDict(from_attributes=True)

class OrderBase(BaseModel):
    cliente_id: int
    data_ordine: Optional[date] = None
    data_richiesta: Optional[date] = None
    data_confermata: Optional[date] = None
    note: Optional[str] = None

class OrderResponse(OrderBase):
    id: int
    numero: int
    anno: int
    numero_completo: str
    stato: str
    totale_imponibile: float
    external_reference: Optional[str] = None
    canale_vendita: str = "diretto"
    cliente: Optional[PartnerResponse] = None
    items: List[OrderItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
