from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class MigrationInspectRequest(BaseModel):
    source_file: str = Field(..., description="Percorso del file .accdb sorgente")

class MigrationInspectResponse(BaseModel):
    is_valid: bool
    source_file: str
    file_size_mb: Optional[float] = None
    tables_count: Optional[int] = None
    tables: List[str] = Field(default_factory=list)
    error: Optional[str] = None

class MigrationDryRunRequest(BaseModel):
    source_file: str

class MigrationDryRunResponse(BaseModel):
    status: str
    source_file: str
    partners_count: int = 0
    products_count: int = 0
    stock_lots_count: int = 0
    delivery_notes_count: int = 0
    invoices_count: int = 0
    installments_count: int = 0
    estimated_seconds: int = 0
    error: Optional[str] = None

class MigrationResetRequest(BaseModel):
    confirm_wipe: str = Field(..., description="Token di conferma 'RESET_ERP9LLI'")

class MigrationResetResponse(BaseModel):
    status: str
    message: str

class MigrationExecuteRequest(BaseModel):
    source_file: str
    is_async: bool = False
    options: Optional[Dict[str, Any]] = None

class MigrationExecuteResponse(BaseModel):
    status: str
    source_file: str
    migrated_partners: int = 0
    migrated_products: int = 0
    migrated_stock_lots: int = 0
    migrated_delivery_notes: int = 0
    migrated_invoices: int = 0
    migrated_installments: int = 0
    task_id: Optional[int] = None
    message: Optional[str] = None

class MigrationUploadResponse(BaseModel):
    status: str
    filename: str
    file_path: str
    file_size_bytes: int
    file_size_mb: float

