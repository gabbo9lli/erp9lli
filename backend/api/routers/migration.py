from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from models import User
from api.deps import require_auth
from schemas.migration import (
    MigrationInspectRequest, MigrationInspectResponse,
    MigrationDryRunRequest, MigrationDryRunResponse,
    MigrationResetRequest, MigrationResetResponse,
    MigrationExecuteRequest, MigrationExecuteResponse
)
from services.legacy_migration_service import LegacyMigrationService
from services.event_dispatcher import dispatch_event

router = APIRouter(prefix="/api/migration", tags=["Legacy Migration"])

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
    return LegacyMigrationService.dry_run(payload.source_file)

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
