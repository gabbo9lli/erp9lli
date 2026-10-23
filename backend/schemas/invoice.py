from typing import Optional, List, Dict, Any
from datetime import date
from pydantic import BaseModel, ConfigDict
from schemas.partner import PartnerResponse
from schemas.product import ProductResponse

class InvoiceInstallmentResponse(BaseModel):
    id: int
    numero_rata: int
    totale_rate: int
    data_scadenza: date
    data_incasso: Optional[date] = None
    importo: float
    stato: str

    model_config = ConfigDict(from_attributes=True)

class InvoiceItemResponse(BaseModel):
    id: int
    delivery_note_id: Optional[int] = None
    product_id: Optional[int] = None
    descrizione: str
    unita_misura: str = "KG"
    colli: int = 1
    quantita: float = 1.0
    prezzo_unitario: float = 0.0
    aliquota_iva: int = 4
    imponibile_riga: float = 0.0
    lotto: Optional[str] = None
    data_scadenza: Optional[date] = None
    product: Optional[ProductResponse] = None

    model_config = ConfigDict(from_attributes=True)

class InvoiceBase(BaseModel):
    cliente_id: int
    tipo_documento: str = "TD01"
    data_documento: date
    condizioni_pagamento: Optional[str] = "30gg fm"
    esigibilita_iva: str = "I"
    note: Optional[str] = None

class InvoiceResponse(InvoiceBase):
    id: int
    numero: int
    anno: int
    numero_completo: str
    totale_imponibile: float
    totale_imposta: float
    totale_fattura: float
    castelletto_iva: Optional[Dict[str, Any]] = None
    stato: str
    invoice_origine_id: Optional[int] = None
    invoice_origine_numero: Optional[str] = None
    causale_storno: Optional[str] = None
    reintegro_magazzino: bool = False
    cliente: Optional[PartnerResponse] = None
    items: List[InvoiceItemResponse] = []
    installments: List[InvoiceInstallmentResponse] = []

    model_config = ConfigDict(from_attributes=True)
