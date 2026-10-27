import os
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from models import Base
from api.websocket_manager import manager
from core.config import settings
from api.routers import (
    auth, system, partners, products, ecommerce,
    orders, delivery_notes, warehouse, invoices,
    accounting, pallets, cmr, pos, labels, events,
    migration
)

# Crea tabelle se non esistono (in dev/sqlite)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="Gestionale Integrato Filiera Ortofrutticola Biologica (ReteBio)",
    version="2.0.0",
    debug=settings.APP_DEBUG
)

# Handler globale per eccezioni HTTP: garantisce standard detail ed error
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "error": detail if isinstance(detail, str) else str(detail)}
    )

import uuid
from core.logging_config import request_id_ctx

# 0. Correlation ID Middleware (X-Request-ID propagation)
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID")
    if not req_id or len(req_id.strip()) == 0:
        req_id = uuid.uuid4().hex
    token = request_id_ctx.set(req_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    finally:
        request_id_ctx.reset(token)

# Configura CORS Middleware con whitelist origini
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Security Headers Middleware (attivo su dev, staging e produzione)
@app.middleware("http")
async def add_security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    if request.url.scheme == "https" or request.headers.get("X-Forwarded-Proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    return response

# 2. Rate Limiting Middleware per gli endpoint di autenticazione
import time
from collections import defaultdict
_auth_rate_limits = defaultdict(list)

@app.middleware("http")
async def auth_rate_limiting_middleware(request: Request, call_next):
    path = request.url.path
    if path in ("/api/signin", "/api/login", "/api/signup", "/api/forgot-password", "/api/reset-password"):
        if not settings.is_testing or request.headers.get("X-Test-Rate-Limit") == "true":
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            window = [t for t in _auth_rate_limits[client_ip] if now - t < 60]
            _auth_rate_limits[client_ip] = window
            if len(window) >= 15:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Too Many Requests", "detail": "Troppi tentativi di autenticazione. Riprova tra 1 minuto."}
                )
            _auth_rate_limits[client_ip].append(now)
    return await call_next(request)

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
app.include_router(migration.router)

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
