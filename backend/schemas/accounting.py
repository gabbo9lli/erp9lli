from typing import Optional, List
from datetime import date
from pydantic import BaseModel, ConfigDict
from schemas.partner import PartnerResponse

class AccountBase(BaseModel):
    codice: str
    nome: str
    tipo: str
    attivo: bool = True

class AccountResponse(AccountBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class AccountingCausalBase(BaseModel):
    codice: str
    descrizione: str
    tipo_registro: str = "generale"
    conto_dare_id: Optional[int] = None
    conto_avere_id: Optional[int] = None
    conto_iva_id: Optional[int] = None
    template_descrizione: Optional[str] = None
    attivo: bool = True

class AccountingCausalResponse(AccountingCausalBase):
    id: int
    conto_dare: Optional[AccountResponse] = None
    conto_avere: Optional[AccountResponse] = None
    conto_iva: Optional[AccountResponse] = None

    model_config = ConfigDict(from_attributes=True)

class JournalItemBase(BaseModel):
    account_id: int
    partner_id: Optional[int] = None
    dare: float = 0.0
    avere: float = 0.0
    descrizione_riga: Optional[str] = None

class JournalItemResponse(JournalItemBase):
    id: int
    account: Optional[AccountResponse] = None
    partner: Optional[PartnerResponse] = None

    model_config = ConfigDict(from_attributes=True)

class JournalEntryBase(BaseModel):
    causale: str
    data_registrazione: date
    data_competenza: Optional[date] = None
    causale_id: Optional[int] = None
    stato: str = "confermata"
    note: Optional[str] = None

class JournalEntryResponse(JournalEntryBase):
    id: int
    numero: int
    anno: int
    numero_completo: str
    totale_dare: float
    totale_avere: float
    causale_operativa: Optional[AccountingCausalResponse] = None
    items: List[JournalItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
