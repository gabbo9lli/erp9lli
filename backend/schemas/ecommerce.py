from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class EcommerceSyncLogResponse(BaseModel):
    id: int
    tipo_operazione: str
    external_order_id: Optional[str] = None
    customer_order_id: Optional[int] = None
    stato: str
    payload_ricevuto: Optional[Dict[str, Any]] = None
    dettaglio_risposta: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class StockFeedItemResponse(BaseModel):
    id: int
    sku: str
    name: str
    price: float
    stock: float
    in_stock: bool
    unita_misura: str = "KG"

    model_config = ConfigDict(from_attributes=True)
