from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict
from schemas.product import ProductResponse

class PosStationBase(BaseModel):
    codice: str
    nome: str
    driver_tipo: str = "simulator"
    ip_address: Optional[str] = None
    porta: int = 80
    matricola_rt: Optional[str] = None
    intestazione: Optional[str] = None
    pie_pagina: Optional[str] = None
    attivo: bool = True

class PosStationResponse(PosStationBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class PosSaleItemResponse(BaseModel):
    id: int
    product_id: int
    quantita: float
    prezzo_unitario: float
    aliquota_iva: float
    subtotale: float
    lotto: Optional[str] = None
    data_scadenza: Optional[date] = None
    product: Optional[ProductResponse] = None

    model_config = ConfigDict(from_attributes=True)

class PosSaleBase(BaseModel):
    pos_station_id: int
    numero_scontrino: str
    data_ora: datetime
    totale_lordo: float
    totale_imponibile: float
    totale_iva: float
    metodo_pagamento: str
    importo_pagato: float
    importo_resto: float = 0.0
    stato: str = "emesso"
    utente_email: Optional[str] = None
    cliente_id: Optional[int] = None

class PosSaleResponse(PosSaleBase):
    id: int
    stato_fiscale_rt: Optional[str] = None
    dettaglio_rt_risposta: Optional[str] = None
    ticket_ascii: Optional[str] = None
    items: List[PosSaleItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
