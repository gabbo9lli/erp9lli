import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from models import Base
from api.routers import auth, system

# Crea tabelle se non esistono (in dev/sqlite)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ERP9lli API",
    description="Gestionale Integrato Filiera Ortofrutticola Biologica (ReteBio)",
    version="2.0.0"
)

# Configura CORS identico a Flask-CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra routers
app.include_router(auth.router)
app.include_router(system.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
