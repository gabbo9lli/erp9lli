#!/usr/bin/env python3
"""
erp9lli - Suite di Test End-to-End su Istanza Live AWS K3s (HTTPS)
Esecuzione: python tests/test_live_e2e.py [TARGET_URL]
"""
import sys
import json
import urllib.request
import urllib.error

TARGET_URL = sys.argv[1] if len(sys.argv) > 1 else "https://18.200.141.146.sslip.io"

print("=" * 70)
print(f"🧪 E2E LIVE TEST SUITE: {TARGET_URL}")
print("=" * 70)

results = []

def record(name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append((name, passed, detail))
    print(f"{status} | {name}" + (f" -> {detail}" if detail else ""))

def get(path, headers=None):
    url = f"{TARGET_URL}{path}"
    req = urllib.request.Request(url, headers=headers or {})
    return urllib.request.urlopen(req)

def post(path, data_dict, headers=None):
    url = f"{TARGET_URL}{path}"
    data = json.dumps(data_dict).encode("utf-8")
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    return urllib.request.urlopen(req)

# 1. Healthcheck & Database Status
try:
    resp = get("/api/health")
    data = json.loads(resp.read().decode())
    passed = data.get("status") == "UP" and data.get("database", {}).get("status") == "UP"
    req_id = resp.headers.get("X-Request-ID")
    record("1. Healthcheck & PostgreSQL Status", passed, f"DB Type: {data.get('database', {}).get('type')}")
    record("1b. X-Request-ID Correlation Header", bool(req_id), f"ID: {req_id}")
except Exception as e:
    record("1. Healthcheck & PostgreSQL Status", False, str(e))
    record("1b. X-Request-ID Correlation Header", False, str(e))

# 2. Security Headers & HSTS
try:
    resp = get("/")
    h = resp.headers
    hsts = h.get("strict-transport-security")
    x_frame = h.get("x-frame-options")
    nosniff = h.get("x-content-type-options")
    passed = bool(hsts) and x_frame == "DENY" and nosniff == "nosniff"
    record("2. Security Headers (HSTS, DENY, nosniff)", passed, f"HSTS: {hsts[:30]}...")
except Exception as e:
    record("2. Security Headers (HSTS, DENY, nosniff)", False, str(e))

# 3. HTTP -> HTTPS Permanent Redirect
try:
    http_url = TARGET_URL.replace("https://", "http://")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    try:
        resp = opener.open(http_url)
        code = resp.getcode()
    except urllib.error.HTTPError as e:
        code = e.code
    passed = code in (301, 308)
    record("3. HTTP to HTTPS 308 Permanent Redirect", passed, f"HTTP Code: {code}")
except Exception as e:
    record("3. HTTP to HTTPS 308 Permanent Redirect", False, str(e))

# 4. CORS Protection
try:
    req_good = urllib.request.Request(f"{TARGET_URL}/api/health", headers={"Origin": TARGET_URL})
    with urllib.request.urlopen(req_good) as r:
        allow_good = r.headers.get("access-control-allow-origin") == TARGET_URL

    req_bad = urllib.request.Request(f"{TARGET_URL}/api/health", headers={"Origin": "https://evil.com"})
    with urllib.request.urlopen(req_bad) as r:
        allow_bad = r.headers.get("access-control-allow-origin") is None

    record("4. CORS Isolation & Whitelist", allow_good and allow_bad, "Allowed domain OK, Evil domain blocked")
except Exception as e:
    record("4. CORS Isolation & Whitelist", False, str(e))

# 5. Autenticazione & JWT Token
token = None
auth_headers = {}
try:
    resp = post("/api/signin", {"email": "dev@example.com", "password": "DevPassword123!"})
    data = json.loads(resp.read().decode())
    token = data.get("access_token")
    auth_headers = {"Authorization": f"Bearer {token}"}
    record("5. User Authentication & JWT Issuance", bool(token), f"Token length: {len(token) if token else 0}")
except Exception as e:
    record("5. User Authentication & JWT Issuance", False, str(e))

# 6. Catalogo Prodotti Biologici
try:
    resp = get("/api/products", headers=auth_headers)
    prods = json.loads(resp.read().decode())
    passed = len(prods) > 0 and any("Bio" in p.get("descrizione", "") for p in prods)
    record("6. Organic Products Catalog API", passed, f"Found {len(prods)} products")
except Exception as e:
    record("6. Organic Products Catalog API", False, str(e))

# 7. Anagrafica Partner
try:
    resp = get("/api/partners", headers=auth_headers)
    partners = json.loads(resp.read().decode())
    passed = len(partners) > 0 and any(p.get("tipo") == "cliente" for p in partners)
    record("7. Partners Directory API", passed, f"Found {len(partners)} partners")
except Exception as e:
    record("7. Partners Directory API", False, str(e))

# 8. Gestione Pallet Legge 182/2025
try:
    resp = get("/api/pallets/types", headers=auth_headers)
    ptypes = json.loads(resp.read().decode())
    has_epal = any(pt.get("codice") == "EPAL" for pt in ptypes)
    record("8. Pallets Interchange L. 182/2025 Types", has_epal, f"Found types: {[pt['codice'] for pt in ptypes]}")
except Exception as e:
    record("8. Pallets Interchange L. 182/2025 Types", False, str(e))

# 9. Contabilità & Piano dei Conti
try:
    resp = get("/api/accounting/accounts", headers=auth_headers)
    accounts = json.loads(resp.read().decode())
    passed = len(accounts) > 0 and any(a.get("codice") == "1001" for a in accounts)
    record("9. General Accounting & Chart of Accounts", passed, f"Found {len(accounts)} accounts")
except Exception as e:
    record("9. General Accounting & Chart of Accounts", False, str(e))

# 10. Event Bus Channels & Outbox
try:
    resp = get("/api/events/channels", headers=auth_headers)
    channels = json.loads(resp.read().decode())
    has_audit = any(c.get("codice") == "AUDIT" for c in channels)
    record("10. Event Bus Channels & Outbox", has_audit, f"Found channels: {[c['codice'] for c in channels]}")
except Exception as e:
    record("10. Event Bus Channels & Outbox", False, str(e))

# 11. Punto Vendita (POS BancoM)
try:
    resp = get("/api/pos/stations", headers=auth_headers)
    stations = json.loads(resp.read().decode())
    passed = len(stations) > 0
    record("11. POS Stations & BancoM API", passed, f"Station: {stations[0].get('nome') if stations else 'None'}")
except Exception as e:
    record("11. POS Stations & BancoM API", False, str(e))

# 11b. Prometheus OpenMetrics Endpoint (/api/metrics)
try:
    resp = get("/api/metrics", headers=auth_headers)
    content = resp.read().decode()
    has_metrics = "erp9lli_http_requests_total" in content and "erp9lli_http_request_duration_seconds" in content
    record("11b. Prometheus OpenMetrics Endpoint", has_metrics, "Found erp9lli_http_requests_total and histograms")
except Exception as e:
    record("11b. Prometheus OpenMetrics Endpoint", False, str(e))

# 11c. Admin Test Alert System Endpoint
try:
    resp = post("/api/system/test-alert", {"message": "Test alert E2E live verification"}, headers=auth_headers)
    data = json.loads(resp.read().decode())
    passed = data.get("status") == "success"
    record("11c. Admin Test Alert System Endpoint", passed, f"Result: {data.get('message')}")
except Exception as e:
    record("11c. Admin Test Alert System Endpoint", False, str(e))

# 11d. Metrics Summary JSON API (/api/metrics/summary)
try:
    resp = get("/api/metrics/summary", headers=auth_headers)
    data = json.loads(resp.read().decode())
    passed = "http" in data and "websockets" in data and "queues_rq" in data and "business_totals" in data
    record("11d. Metrics Summary JSON API", passed, f"Avg Latency: {data.get('http', {}).get('avg_latency_ms')}ms, WS: {data.get('websockets', {}).get('active_clients')}")
except Exception as e:
    record("11d. Metrics Summary JSON API", False, str(e))

# 11e. Grafana External Dashboard Ingress (/grafana)
try:
    resp = get("/grafana/")
    code = resp.getcode()
    passed = code in (200, 302)
    record("11e. Grafana Dashboard Ingress (/grafana)", passed, f"HTTP Code: {code}")
except Exception as e:
    record("11e. Grafana Dashboard Ingress (/grafana)", False, str(e))

# 12. Rate Limiting Anti Brute-Force (eseguito alla fine per non bloccare i test precedenti)
try:
    auth_url = f"{TARGET_URL}/api/signin"
    bad_creds = json.dumps({"email": "fake@test.com", "password": "wrong"}).encode()
    throttled = False
    for _ in range(25):
        req = urllib.request.Request(auth_url, data=bad_creds, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                throttled = True
                break
    record("12. Anti Brute-Force Rate Limiting (429)", throttled, "HTTP 429 triggered as expected")
except Exception as e:
    record("12. Anti Brute-Force Rate Limiting (429)", False, str(e))

print("=" * 70)
total_tests = len(results)
passed_tests = sum(1 for _, p, _ in results if p)
print(f"📊 RIEPILOGO TEST LIVE: {passed_tests}/{total_tests} superati")
print("=" * 70)

if passed_tests < total_tests:
    sys.exit(1)
sys.exit(0)
