import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from database import get_db, engine
from api.deps import require_auth
from models import User
from core.config import settings

router = APIRouter(prefix="/api", tags=["System"])

AVAILABLE_MODULES = [
    "anagrafiche", "orders", "delivery_notes", "invoicing",
    "accounting", "warehouse", "pallets", "cmr", "pos", "ecommerce"
]

@router.get("/modules")
def get_enabled_modules():
    return {mod: settings.is_module_enabled(mod) for mod in AVAILABLE_MODULES}

@router.get("/health")
def health(db: Session = Depends(get_db)):
    health_status = {
        "status": "UP",
        "fastapi_status": "UP",
        "database": {
            "status": "DOWN",
            "type": settings.DB_TYPE,
            "connection_error": None
        }
    }
    try:
        db.execute(text('SELECT 1'))
        health_status["database"]["status"] = "UP"
    except Exception as e:
        health_status["database"]["connection_error"] = str(e)

    return health_status

@router.get("/db-explorer")
def db_explorer(current_user: User = Depends(require_auth(roles=['Admin'])), db: Session = Depends(get_db)):
    inspector = inspect(db.bind or engine)
    tables = inspector.get_table_names()

    db_info = []
    for table_name in tables:
        try:
            res = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
        except Exception:
            res = 0

        columns = [col['name'] for col in inspector.get_columns(table_name)]

        db_info.append({
            "name": table_name,
            "rows": res,
            "columns": columns
        })

    return {
        "engine": (db.bind or engine).name,
        "tables": db_info
    }

@router.get("/db-explorer/{table_name}/data")
def get_table_data(table_name: str, current_user: User = Depends(require_auth(roles=['Admin'])), db: Session = Depends(get_db)):
    inspector = inspect(db.bind or engine)
    if table_name not in inspector.get_table_names():
        return JSONResponse(status_code=404, content={"error": "Table not found"})
    try:
        result = db.execute(text(f"SELECT * FROM {table_name} LIMIT 10"))
        columns = result.keys()
        data = [dict(zip(columns, row)) for row in result]
        return {"data": data}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
