# Spec: Observability, Metriche Prometheus & Multi-Channel Alerting

**Data:** 26 Ottobre 2026  
**Autore:** Team di Sviluppo erp9lli  
**Stato:** Approvato (Pronto per Piano di Implementazione)  
**Percorso Documento:** `docs/superpowers/specs/2026-10-26-observability-metrics-alerting-design.md`  

---

## 1. Obiettivo e Visione

Dotare **erp9lli** di un sottosistema di osservabilità e monitoraggio proattivo conforme agli standard Cloud Native (CNCF) senza appesantire le risorse dell'infrastruttura a basso costo su AWS EC2 Graviton:

1. **Structured JSON Logging & Correlation ID:** Tracciamento end-to-end di ogni richiesta tramite header e contextvar `X-Request-ID`, con emissione di log strutturati in formato JSON in produzione;
2. **Metriche OpenMetrics / Prometheus (`/metrics`):** Esposizione nativa delle metriche applicative, infrastrutturali e di business senza dipendere da container pesanti terzi;
3. **Multi-Channel Alerting con Anti-Flapping:** Notifica immediata di anomalie critiche (errori HTTP 500 ed eccezioni nei job asincroni RQ) verso Webhook generico (Slack/Discord/Teams/Mattermost), Bot Telegram e canale Email dell'Event Bus, con protezione da spam tramite cooldown su fingerprinting dell'eccezione.

---

## 2. Architettura dei Componenti

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Application Core                        │
├────────────────────────────────────────────────────────────────────────┤
│ 1. CorrelationIdMiddleware                                             │
│    - Estrae o genera X-Request-ID (UUIDv4)                             │
│    - Imposta contextvar request_id                                     │
│    - Inietta X-Request-ID negli header di risposta HTTP                │
├────────────────────────────────────────────────────────────────────────┤
│ 2. StructuredJSONLogger & AccessLogMiddleware                           │
│    - Formatta i log in JSON in prod/docker, testuale in dev            │
│    - Registra metodo, path, status, duration_ms, user, ip e request_id │
├────────────────────────────────────────────────────────────────────────┤
│ 3. MetricsCollector & Prometheus Endpoint (/metrics)                   │
│    - Ingress/HTTP: requests_total, request_duration_seconds            │
│    - WebSockets: active_connections, broadcast_total                   │
│    - Code Redis RQ: queue_jobs_count, failed_jobs_count                │
│    - Business ERP: orders_total, invoices_total, pos_sales_total       │
├────────────────────────────────────────────────────────────────────────┤
│ 4. AlertingService (backend/services/alerting_service.py)              │
│    - Trigger: Global 500 ExceptionHandler e RQ OnFailure Hook          │
│    - Calcolo fingerprint errore (MD5 tipo + file + linea)              │
│    - Cooldown anti-flapping (5 minuti)                                 │
│    - Dispatcher: Webhook HTTP, Telegram Bot API, Event Bus EMAIL       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Specifiche di Dettaglio

### 3.1 Correlation ID & Structured Logging
- **`backend/core/logging_config.py`:**
  - Definizione di `request_id_ctx = ContextVar("request_id", default=None)`;
  - Formatter personalizzato `JSONLogFormatter`:
    ```json
    {
      "timestamp": "2026-10-26T16:04:12.123Z",
      "level": "INFO",
      "logger": "erp9lli.api",
      "request_id": "c4b8e21a-63d1-4f89-8d7b-91f82e0d3a12",
      "method": "POST",
      "path": "/api/invoices",
      "status_code": 201,
      "duration_ms": 18.4,
      "client_ip": "18.200.141.146",
      "user_email": "dev@example.com",
      "message": "Fattura emessa con successo"
    }
    ```
  - In ambiente `development` (su terminale locale) il formato rimane testuale leggibile con timestamp e colori, mentre se `APP_ENV=production` o in container Docker viene forzato il JSON compatto;
- **Middleware `CorrelationIdMiddleware`:**
  - Registrato come primo middleware ASGI per intercettare qualsiasi richiesta in ingresso;
  - Se il client invia già `X-Request-ID`, lo preserva e valida; altrimenti genera un nuovo `uuid.uuid4().hex`.

---

### 3.2 Catalogo Metriche Prometheus (`/metrics`)
Implementato con la libreria `prometheus_client` ed esposto sull'endpoint `GET /metrics`:

| Metrica | Tipo | Label | Descrizione |
|---|---|---|---|
| `erp9lli_http_requests_total` | Counter | `method`, `endpoint`, `status` | Conteggio totale chiamate HTTP |
| `erp9lli_http_request_duration_seconds` | Histogram | `method`, `endpoint` | Latenza chiamate HTTP (bucket: 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10s) |
| `erp9lli_http_requests_in_progress` | Gauge | `method`, `endpoint` | Richieste attualmente in elaborazione |
| `erp9lli_websocket_active_connections` | Gauge | — | Connessioni client contemporanee su `/ws` |
| `erp9lli_websocket_broadcast_total` | Counter | `action` | Messaggi broadcast emessi (`created`, `progress`, `completed`, `error`) |
| `erp9lli_rq_queue_jobs_count` | Gauge | `queue` | Numero di job in attesa nelle code Redis (`critical`, `emails`, `reports`, `default`) |
| `erp9lli_rq_failed_jobs_count` | Gauge | `queue` | Numero di job falliti nelle code Redis |
| `erp9lli_orders_created_total` | Counter | — | Totale ordini clienti inseriti nel sistema |
| `erp9lli_invoices_created_total` | Counter | `tipo_documento` | Totale fatture (`TD01`, `TD24`) e note di credito (`TD04`) |
| `erp9lli_pos_sales_created_total` | Counter | `metodo_pagamento` | Totale vendite al banco registrate (`contanti`, `pos_carta`) |
| `erp9lli_migration_runs_total` | Counter | `status` | Esecuzioni del modulo di migrazione (`success`, `error`) |

*Nota di sicurezza di rete:* L'endpoint `/metrics` è accessibile internamente nel cluster K3s su porta 8000 per Prometheus/VictoriaMetrics o in locale su `http://localhost:5000/metrics`. Non è instradato pubblicamente su Traefik verso Internet.

---

### 3.3 Multi-Channel Error Alerting con Anti-Flapping

#### Configurazione (`backend/core/config.py`):
- `ALERT_WEBHOOK_URL: Optional[str] = None` (URL Webhook generico: Slack, Discord, MS Teams, Mattermost);
- `TELEGRAM_BOT_TOKEN: Optional[str] = None` (Token API del Bot Telegram, es. `123456:ABC-DEF...`);
- `TELEGRAM_CHAT_ID: Optional[str] = None` (ID chat o canale Telegram di destinazione, es. `-100123456789`);
- `ALERT_EMAIL_RECIPIENT: Optional[str] = None` (Email per invio alert tramite canale EMAIL dell'Event Bus);
- `ALERT_COOLDOWN_SECONDS: int = 300` (Default 5 minuti di cooldown anti-spam per errori identici).

#### Logica di `AlertingService`:
1. **Fingerprinting & Anti-Flapping:**
   - All'arrivo di un errore viene calcolato l'hash: `fingerprint = hashlib.md5(f"{type(exc).__name__}:{exc.__traceback__.tb_frame.f_code.co_filename}:{exc.__traceback__.tb_lineno}".encode()).hexdigest()`;
   - Se il `fingerprint` è presente nella cache in memoria e il tempo trascorso è minore di `ALERT_COOLDOWN_SECONDS`, la notifica esterna viene soppressa;
2. **Invio Multi-Canale (Parallelo e Non-Bloccante):**
   - **Canale 1 (Webhook):** Se `ALERT_WEBHOOK_URL` è configurato, invia una richiesta HTTP POST con payload JSON standard (compatibile con Slack formatting o JSON generico `{"text": ...}`);
   - **Canale 2 (Telegram):** Se `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` sono configurati, invia `POST https://api.telegram.org/bot<TOKEN>/sendMessage` con `parse_mode=Markdown`;
   - **Canale 3 (Event Bus):** Se `ALERT_EMAIL_RECIPIENT` è valorizzato, genera un `SystemEvent` sul canale `EMAIL` / categoria `SISTEMA`;
3. **Punti di Innesco:**
   - Exception Handler globale HTTP 500 in `backend/main.py`: intercetta qualsiasi eccezione non gestita;
   - Hook di fallimento per i job asincroni in `event_dispatcher.py` / worker RQ;
   - Endpoint di collaudo per l'amministratore: `POST /api/system/test-alert` (richiede ruolo `Admin`).

---

## 4. Strategia di Test & Validazione

1. **Test Unit & Integration (`tests/backend/test_observability.py`):**
   - Test propagazione e generazione `X-Request-ID` nelle risposte HTTP;
   - Test endpoint `GET /metrics`: verifica presenza di tutte le metriche (HTTP, WebSocket, code, ordini, fatture);
   - Test `AlertingService`:
     - Test mock invio webhook e telegram su errore;
     - Test anti-flapping: due chiamate consecutive con stesso errore producono 1 solo invio esterno;
     - Test endpoint di collaudo `POST /api/system/test-alert`.
2. **Regression Test:** Esecuzione dell'intera suite backend (110 test) e frontend (28 test) per garantire zero impatto prestazionale e zero regressioni.
