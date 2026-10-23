import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from models import Base
from api.websocket_manager import manager
from api.routers import (
    auth, system, partners, products, ecommerce,
    orders, delivery_notes, warehouse, invoices,
    accounting, pallets, cmr, pos, labels, events
)

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
app.include_router(partners.router)
app.include_router(products.router)
app.include_router(ecommerce.router)
app.include_router(orders.router)
app.include_router(delivery_notes.router)
app.include_router(warehouse.router)
app.include_router(invoices.router)
app.include_router(accounting.router)
app.include_router(pallets.router)
app.include_router(cmr.router)
app.include_router(pos.router)
app.include_router(labels.router)
app.include_router(events.router)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
