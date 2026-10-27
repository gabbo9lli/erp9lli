# Observability, Metriche Prometheus & Multi-Channel Alerting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a production-grade observability and proactive monitoring subsystem featuring structured JSON logging with correlation IDs, Prometheus OpenMetrics `/metrics` endpoint, and a multi-channel anti-flapping error alerting service.

**Architecture:** Conforms to Clean Architecture: contextvar-based `CorrelationIdMiddleware` and `JSONLogFormatter` in `backend/core/logging_config.py`, native OpenMetrics instrumentation via `prometheus_client` in `backend/core/metrics.py`, and multi-channel alerting (`AlertingService`) dispatched on unhandled 500s, RQ failures, and admin test endpoints.

**Tech Stack:** Python 3.11, FastAPI, `prometheus-client`, `contextvars`, `requests` / `urllib`, Redis RQ, Pytest.

**Spec:** `docs/superpowers/specs/2026-10-26-observability-metrics-alerting-design.md`

## Global Constraints

- Never block HTTP request processing if external alerting webhooks or Telegram APIs fail or timeout; alerts must run safely with exception handling.
- Anti-flapping cooldown must enforce a default 5-minute silence window for identical exception fingerprints.
- The `/metrics` endpoint must adhere strictly to OpenMetrics/Prometheus plain text formatting.
- Git commits must always be signed with key `8B91C26B23264F4407CD41343FD13DC88C48D7E0` and author `gabbo <gabbo9lli@gmail.com>`.

## Review Focus

- Correlation ID must be returned in the `X-Request-ID` response header for every HTTP request (including 4xx and 5xx errors).
- Calling `/metrics` multiple times must return consistent valid prometheus metric names without re-registration errors.
- Unhandled 500 exceptions must trigger the alerting service while returning a sanitized JSON response containing `request_id` to the client.
- Alerting service must not trigger external HTTP calls when cooldown is active for the same error fingerprint.

---

### Task 1: Correlation ID & Structured JSON Logging

**Files:**
- Create: `backend/core/logging_config.py`
- Modify: `backend/main.py`
- Create: `tests/backend/test_observability.py`

**Interfaces:**
- Produces: `request_id_ctx` ContextVar, `JSONLogFormatter`, and `CorrelationIdMiddleware` setting `X-Request-ID` in headers.

- [ ] **Step 1: Scrivere test per generazione e propagazione di `X-Request-ID`**

```python
# in tests/backend/test_observability.py
def test_correlation_id_generated_and_propagated(client):
    # Generato se assente
    r1 = client.get("/api/health")
    assert r1.status_code == 200
    assert "X-Request-ID" in r1.headers
    req_id = r1.headers["X-Request-ID"]
    assert len(req_id) >= 16

    # Preservato se fornito dal client
    custom_id = "test-custom-request-id-12345"
    r2 = client.get("/api/health", headers={"X-Request-ID": custom_id})
    assert r2.status_code == 200
    assert r2.headers["X-Request-ID"] == custom_id
```

- [ ] **Step 2: Eseguire il test per verificare il fallimento (RED)**

Run: `uv run --offline --with-requirements backend/requirements.txt pytest tests/backend/test_observability.py -k test_correlation_id_generated_and_propagated -v`
Expected: FAIL with `KeyError: 'X-Request-ID'`

- [ ] **Step 3: Implementare `backend/core/logging_config.py` e il middleware in `backend/main.py`**

Creare `backend/core/logging_config.py` con `request_id_ctx`, formatter JSON per produzione e testuale per dev. Aggiungere il middleware `CorrelationIdMiddleware` in `backend/main.py` che valorizza il contextvar e inietta l'header `X-Request-ID` nella risposta.

- [ ] **Step 4: Eseguire il test per verificare il passaggio (GREEN)**

Run: `uv run --offline --with-requirements backend/requirements.txt pytest tests/backend/test_observability.py -k test_correlation_id_generated_and_propagated -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/logging_config.py backend/main.py tests/backend/test_observability.py
git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat(observability): correlation ID contextvar, middleware e structured logging"
```

---

### Task 2: Metriche Prometheus OpenMetrics & Endpoint `/metrics`

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/core/metrics.py`
- Modify: `backend/main.py`
- Modify: `backend/api/websocket_manager.py`
- Modify: `tests/backend/test_observability.py`

**Interfaces:**
- Produces: Prometheus counters/histograms/gauges e endpoint `GET /metrics`.

- [ ] **Step 1: Scrivere test per l'endpoint `/metrics` e le metriche di dominio**

```python
# in tests/backend/test_observability.py
def test_prometheus_metrics_endpoint(client):
    # Eseguiamo una chiamata per incrementare i contatori
    client.get("/api/health")

    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["Content-Type"] or "application/openmetrics-text" in r.headers["Content-Type"]
    content = r.text
    assert "erp9lli_http_requests_total" in content
    assert "erp9lli_http_request_duration_seconds" in content
    assert "erp9lli_websocket_active_connections" in content
    assert "erp9lli_orders_created_total" in content
```

- [ ] **Step 2: Eseguire il test per verificare il fallimento (RED)**

Run: `uv run --offline --with-requirements backend/requirements.txt pytest tests/backend/test_observability.py -k test_prometheus_metrics_endpoint -v`
Expected: FAIL with status 404 Not Found

- [ ] **Step 3: Implementare `backend/core/metrics.py` e collegare l'endpoint `/metrics` in `backend/main.py`**

Aggiungere `prometheus-client` a `backend/requirements.txt`. Creare `backend/core/metrics.py` con le metriche specificate nella spec (HTTP, WebSocket, code RQ, ordini/fatture). Aggiungere middleware per tracciare le metriche HTTP e registrare `GET /metrics` in `main.py`. Aggiornare `websocket_manager.py` per tracciare `active_connections`.

- [ ] **Step 4: Eseguire il test per verificare il passaggio (GREEN)**

Run: `uv run --offline --with-requirements backend/requirements.txt pytest tests/backend/test_observability.py -k test_prometheus_metrics_endpoint -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/core/metrics.py backend/main.py backend/api/websocket_manager.py tests/backend/test_observability.py
git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat(observability): metriche Prometheus OpenMetrics ed endpoint /metrics"
```

---

### Task 3: Multi-Channel Alerting Service con Anti-Flapping

**Files:**
- Modify: `backend/core/config.py`
- Create: `backend/services/alerting_service.py`
- Modify: `backend/main.py`
- Modify: `backend/api/routers/system.py`
- Modify: `tests/backend/test_observability.py`

**Interfaces:**
- Produces: `AlertingService.notify_error(exc, request, context)`, `POST /api/system/test-alert`.

- [ ] **Step 1: Scrivere test per `AlertingService`, anti-flapping e endpoint di test**

```python
# in tests/backend/test_observability.py
def test_alerting_service_multi_channel_and_cooldown(monkeypatch):
    from services.alerting_service import AlertingService

    sent_webhooks = []
    def mock_post(url, json=None, data=None, timeout=None):
        sent_webhooks.append((url, json or data))
        class MockResp:
            status_code = 200
        return MockResp()

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: None)
    monkeypatch.setattr("services.alerting_service.AlertingService._send_http_request", mock_post)

    # 1. Primo errore -> genera alert
    res1 = AlertingService.notify_error(ValueError("Errore di test 1"), endpoint="/api/test")
    assert res1["notified"] is True

    # 2. Stesso errore immediato -> bloccato da cooldown
    res2 = AlertingService.notify_error(ValueError("Errore di test 1"), endpoint="/api/test")
    assert res2["notified"] is False
    assert res2["reason"] == "cooldown_active"
```

- [ ] **Step 2: Eseguire il test per verificare il fallimento (RED)**

Run: `uv run --offline --with-requirements backend/requirements.txt pytest tests/backend/test_observability.py -k test_alerting_service_multi_channel_and_cooldown -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.alerting_service'`

- [ ] **Step 3: Implementare `AlertingService` e collegare l'exception handler 500 globale**

Implementare in `backend/services/alerting_service.py` fingerprinting, cooldown cache in memoria (5 minuti), dispatching su Webhook generico, Telegram e canale EMAIL dell'Event Bus. Registrare l'invocazione di `AlertingService` nell'exception handler globale 500 in `backend/main.py`. Aggiungere endpoint `POST /api/system/test-alert` in `backend/api/routers/system.py` per test amministrativi.

- [ ] **Step 4: Eseguire il test per verificare il passaggio (GREEN)**

Run: `uv run --offline --with-requirements backend/requirements.txt pytest tests/backend/test_observability.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/config.py backend/services/alerting_service.py backend/main.py backend/api/routers/system.py tests/backend/test_observability.py
git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat(observability): AlertingService multi-canale (Webhook, Telegram, Email) con anti-flapping"
```

---

### Task 4: Verifica Completa, Aggiornamento Suite Live & Deploy Cloud

**Files:**
- Modify: `tests/test_live_e2e.py`
- Modify: `k8s/01-configmap.yaml`
- Modify: `k8s/02-secrets.yaml`

**Interfaces:**
- Produces: Test E2E aggiornati che validano `X-Request-ID` e `/metrics` sull'istanza live AWS.

- [ ] **Step 1: Aggiornare lo script `tests/test_live_e2e.py` con verifiche di osservabilità**

Aggiungere verifiche live per:
- Presenza dell'header `X-Request-ID` su tutte le risposte HTTPS;
- Validazione risposta `GET /metrics` su backend.

- [ ] **Step 2: Eseguire la test suite locale completa (Backend & Frontend)**

Run: `uv run --offline --with-requirements backend/requirements.txt pytest tests/backend/ -q && npm test --prefix frontend`
Expected: 100% green (110+ backend test, 28 frontend test).

- [ ] **Step 3: Commit, Push e Rollout su cluster AWS K3s**

```bash
git add tests/test_live_e2e.py k8s/
git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "test(observability): verifiche E2E live per request-id e metriche prometheus"
git push origin main
```
Rollout dei nuovi pod backend su AWS e verifica finale con `python3 tests/test_live_e2e.py`.
