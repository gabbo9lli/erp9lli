from typing import Optional
from pydantic import BaseModel, ConfigDict

class PartnerBase(BaseModel):
    ragione_sociale: str
    tipo: str = "cliente"
    partita_iva: Optional[str] = None
    codice_fiscale: Optional[str] = None
    indirizzo: Optional[str] = None
    cap: Optional[str] = None
    citta: Optional[str] = None
    provincia: Optional[str] = None
    nazione: str = "IT"
    codice_sdi: str = "0000000"
    pec: Optional[str] = None
    istituto_certificatore: Optional[str] = None
    iban: Optional[str] = None
    condizioni_pagamento: str = "30gg fm"
    attivo: bool = True

class PartnerCreate(BaseModel):
    ragione_sociale: str
    tipo: Optional[str] = "cliente"
    partita_iva: Optional[str] = None
    codice_fiscale: Optional[str] = None
    indirizzo: Optional[str] = None
    cap: Optional[str] = None
    citta: Optional[str] = None
    provincia: Optional[str] = None
    nazione: Optional[str] = "IT"
    codice_sdi: Optional[str] = "0000000"
    pec: Optional[str] = None
    istituto_certificatore: Optional[str] = None
    iban: Optional[str] = None
    condizioni_pagamento: Optional[str] = "30gg fm"
    attivo: Optional[bool] = True

class PartnerUpdate(BaseModel):
    ragione_sociale: Optional[str] = None
    tipo: Optional[str] = None
    partita_iva: Optional[str] = None
    codice_fiscale: Optional[str] = None
    indirizzo: Optional[str] = None
    cap: Optional[str] = None
    citta: Optional[str] = None
    provincia: Optional[str] = None
    nazione: Optional[str] = None
    codice_sdi: Optional[str] = None
    pec: Optional[str] = None
    istituto_certificatore: Optional[str] = None
    iban: Optional[str] = None
    condizioni_pagamento: Optional[str] = None
    attivo: Optional[bool] = None

class PartnerResponse(PartnerBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
