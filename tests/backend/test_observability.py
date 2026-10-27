import pytest

def test_correlation_id_generated_and_propagated(client):
    # 1. Generato automaticamente se assente nella richiesta
    r1 = client.get("/api/health")
    assert r1.status_code == 200
    assert "X-Request-ID" in r1.headers
    req_id = r1.headers["X-Request-ID"]
    assert len(req_id) >= 16

    # 2. Preservato se fornito dal client
    custom_id = "test-custom-request-id-12345"
    r2 = client.get("/api/health", headers={"X-Request-ID": custom_id})
    assert r2.status_code == 200
    assert r2.headers["X-Request-ID"] == custom_id

def test_json_log_formatter_includes_request_id():
    import logging
    import json
    from core.logging_config import JSONLogFormatter, request_id_ctx
    formatter = JSONLogFormatter()
    request_id_ctx.set("custom-trace-uuid-999")
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Messaggio di test log",
        args=(),
        exc_info=None
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "Messaggio di test log"
    assert parsed["request_id"] == "custom-trace-uuid-999"

def test_prometheus_metrics_endpoint(client):
    # Eseguiamo una chiamata per incrementare i contatori
    client.get("/api/health")

    r = client.get("/metrics")
    assert r.status_code == 200
    content = r.text
    assert "erp9lli_http_requests_total" in content
    assert "erp9lli_http_request_duration_seconds" in content
    assert "erp9lli_websocket_active_connections" in content
    assert "erp9lli_orders_created_total" in content

def test_alerting_service_multi_channel_and_cooldown(monkeypatch):
    from services.alerting_service import AlertingService
    from core.config import settings

    sent_requests = []
    def mock_http_request(url, payload):
        sent_requests.append((url, payload))
        return True

    monkeypatch.setattr("services.alerting_service.AlertingService._send_http_request", mock_http_request)
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_URL", "https://hooks.slack.com/services/test/mock/webhook")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456:MOCK_TOKEN")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "-1001234567")

    # 1. Primo errore -> genera alert su webhook e telegram
    res1 = AlertingService.notify_error(ValueError("Errore di test 1"), endpoint="/api/test", request_id="trace-001")
    assert res1["notified"] is True
    assert len(sent_requests) == 2  # 1 webhook + 1 telegram

    # 2. Stesso errore immediato -> bloccato da cooldown
    res2 = AlertingService.notify_error(ValueError("Errore di test 1"), endpoint="/api/test", request_id="trace-002")
    assert res2["notified"] is False
    assert res2["reason"] == "cooldown_active"
    assert len(sent_requests) == 2  # nessun nuovo invio

def test_api_system_test_alert_endpoint(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    r = client.post("/api/system/test-alert", json={"message": "Alert di collaudo manuale"}, headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"

def test_api_metrics_summary_endpoint(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    client.get('/api/health')

    r = client.get('/api/metrics/summary', headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "http" in data
    assert "websockets" in data
    assert "queues_rq" in data
    assert "business_totals" in data
    assert data["http"]["total_requests"] >= 1
    assert "avg_latency_ms" in data["http"]
    assert "active_clients" in data["websockets"]




