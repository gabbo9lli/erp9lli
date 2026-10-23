from typing import Optional
from pydantic import BaseModel, ConfigDict

class ProductBase(BaseModel):
    codice: str
    descrizione: str
    categoria: str = "fresco"
    unita_misura: str = "KG"
    peso_netto: Optional[float] = None
    prezzo_vendita: float = 0.0
    prezzo_acquisto: float = 0.0
    aliquota_iva: int = 4
    in_scadenza: bool = False
    giorni_shelf_life: Optional[int] = None
    codice_nc: Optional[str] = None
    attivo: bool = True

class ProductCreate(BaseModel):
    codice: str
    descrizione: str
    categoria: Optional[str] = "fresco"
    unita_misura: Optional[str] = "KG"
    peso_netto: Optional[float] = None
    prezzo_vendita: Optional[float] = 0.0
    prezzo_acquisto: Optional[float] = 0.0
    aliquota_iva: Optional[int] = 4
    in_scadenza: Optional[bool] = False
    giorni_shelf_life: Optional[int] = None
    codice_nc: Optional[str] = None
    attivo: Optional[bool] = True

class ProductUpdate(BaseModel):
    codice: Optional[str] = None
    descrizione: Optional[str] = None
    categoria: Optional[str] = None
    unita_misura: Optional[str] = None
    peso_netto: Optional[float] = None
    prezzo_vendita: Optional[float] = None
    prezzo_acquisto: Optional[float] = None
    aliquota_iva: Optional[int] = None
    in_scadenza: Optional[bool] = None
    giorni_shelf_life: Optional[int] = None
    codice_nc: Optional[str] = None
    attivo: Optional[bool] = None

class ProductResponse(ProductBase):
    id: int
    margine_unitario: Optional[float] = None
    percentuale_ricarico: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)
