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


