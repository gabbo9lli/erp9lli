import os
import shutil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from models import User
from api.deps import require_auth
from schemas.migration import (
    MigrationInspectRequest, MigrationInspectResponse,
    MigrationDryRunRequest, MigrationDryRunResponse,
    MigrationResetRequest, MigrationResetResponse,
    MigrationExecuteRequest, MigrationExecuteResponse,
    MigrationUploadResponse
)
from services.legacy_migration_service import LegacyMigrationService
from services.event_dispatcher import dispatch_event

router = APIRouter(prefix="/api/migration", tags=["Legacy Migration"])

ALLOWED_EXTENSIONS = {".accdb", ".mdb"}
UPLOAD_DIR = os.environ.get("LEGACY_UPLOAD_DIR", "/tmp/legacy_uploads")

@router.post("/upload", response_model=MigrationUploadResponse)
def upload_legacy_database(
    file: UploadFile = File(...),
    current_user: User = Depends(require_auth(roles=['Admin']))
):
    original_name = file.filename or "database.accdb"
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Estensione file non valida. Sono supportati solo database Access (.accdb, .mdb)"
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    clean_base = os.path.basename(original_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_filename = f"{timestamp}_{clean_base}"
    target_path = os.path.join(UPLOAD_DIR, target_filename)

    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    size_bytes = os.path.getsize(target_path)
    size_mb = round(size_bytes / (1024 * 1024), 2)

    return {
        "status": "success",
        "filename": original_name,
        "file_path": target_path,
        "file_size_bytes": size_bytes,
        "file_size_mb": size_mb
    }

@router.post("/inspect", response_model=MigrationInspectResponse)
def inspect_legacy_database(
    payload: MigrationInspectRequest,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    return LegacyMigrationService.inspect_database(payload.source_file)

@router.post("/dry-run", response_model=MigrationDryRunResponse)
def dry_run_legacy_database(
    payload: MigrationDryRunRequest,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    res = LegacyMigrationService.dry_run(payload.source_file)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@router.post("/reset", response_model=MigrationResetResponse)
def reset_database_endpoint(
    payload: MigrationResetRequest,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    return LegacyMigrationService.reset_database(db, payload.confirm_wipe)

@router.post("/execute", response_model=MigrationExecuteResponse, status_code=status.HTTP_201_CREATED)
def execute_legacy_migration(
    payload: MigrationExecuteRequest,
    current_user: User = Depends(require_auth(roles=['Admin'])),
    db: Session = Depends(get_db)
):
    if payload.is_async:
        def _async_migration(event):
            import database
            with database.SessionLocal() as session:
                LegacyMigrationService.run_full_migration(
                    session,
                    payload.source_file,
                    payload.options,
                    event=event
                )

        ev = dispatch_event(
            channel_code="AUDIT",
            category_code="SISTEMA",
            azione="migrazione_legacy",
            titolo="Migrazione Dati Legacy Access",
            descrizione=f"Importazione da {payload.source_file}",
            is_async=True,
            target_func=_async_migration,
            db=db
        )
        return {
            "status": "in_coda",
            "source_file": payload.source_file,
            "task_id": ev.id,
            "message": "Migrazione avviata in background con monitoraggio live via WebSockets"
        }
    else:
        res = LegacyMigrationService.run_full_migration(db, payload.source_file, payload.options)
        return res
