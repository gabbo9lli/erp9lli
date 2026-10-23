from typing import Optional, List, Dict
from datetime import date
from pydantic import BaseModel, ConfigDict
from schemas.partner import PartnerResponse

class PalletTypeBase(BaseModel):
    codice: str
    descrizione: str
    materiale: str = "legno"
    valore_risarcimento: float = 18.0
    attivo: bool = True

class PalletTypeResponse(PalletTypeBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class PalletReceiptItemResponse(BaseModel):
    id: int
    pallet_type_id: int
    quantita_consegnata: int
    quantita_restituita: int
    saldo_riga: int
    pallet_type: Optional[PalletTypeResponse] = None

    model_config = ConfigDict(from_attributes=True)

class PalletReceiptBase(BaseModel):
    partner_id: int
    data_emissione: date
    data_limite_restituzione: Optional[date] = None
    delivery_note_id: Optional[int] = None
    tipo: str = "uscita"
    note: Optional[str] = None

class PalletReceiptResponse(PalletReceiptBase):
    id: int
    numero: int
    anno: int
    numero_completo: str
    totale_consegnati: int
    totale_restituiti: int
    saldo_netto: int
    stato: str
    partner: Optional[PartnerResponse] = None
    items: List[PalletReceiptItemResponse] = []

    model_config = ConfigDict(from_attributes=True)

class PalletLedgerItemResponse(BaseModel):
    partner_id: int
    partner_nome: str
    partner_tipo: str
    saldi: Dict[str, int]
    totale_bancali_debito: int
    buoni_aperti_count: int
    buoni_scaduti_count: int

    model_config = ConfigDict(from_attributes=True)
