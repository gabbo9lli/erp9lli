# Traefik v3 + oauth2-proxy (ForwardAuth OIDC) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare l'autenticazione federata OIDC con architettura Full Edge Auth tramite Traefik v3, oauth2-proxy (ForwardAuth), auto-provisioning nel backend Flask e gestione della sessione SSO nel frontend Vue 3.

**Architecture:** Traefik v3 gestisce TLS, security headers e routing Docker. oauth2-proxy gestisce il flusso OIDC e valida i cookie crittografati, iniettando header di identità (`X-Forwarded-*`). Il backend Flask esegue l'auto-provisioning nel database locale PostgreSQL leggendo questi header e applicando il role mapping; il frontend Vue 3 interroga `/api/me` e supporta login/logout SSO federati.

**Tech Stack:** Docker Compose, Traefik v3.1, oauth2-proxy v7.6.0, Python 3.11, Flask, SQLAlchemy, Vue 3, Quasar, Vitest, Pytest.

**Spec:** `docs/superpowers/specs/2026-10-19-traefik-oauth2-proxy-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **Compatibilità Sviluppo Locale:** In ambiente `development` (`docker-compose.override.yaml`), Flask deve consentire il fallback automatico su `DEV_AUTH_USER` per permettere lo sviluppo senza un IdP cloud attivo.
- **TDD:** Ogni componente nuovo o modificato deve avere il proprio test unitario verificato prima di dichiarare completato il task.

## Review Focus

1. **Auto-provisioning & Unicità Utente:** Utenti con la stessa email non devono essere duplicati; utenti nuovi devono essere creati con username univoco e ruolo coerente con i claims.
2. **Accesso Anonimo Rifiutato:** Endpoint protetti devono restituire 401 se invocati in produzione senza header `X-Forwarded-Email`.
3. **Controllo Ruoli (RBAC):** Utenti con ruolo `User` non devono poter accedere a rotte riservate a `Admin` (403 Forbidden).
4. **Coerenza Docker Compose Traefik:** Il parsing di `docker-compose.prod.yaml` deve passare la validazione sintattica con `docker compose config`.
5. **Sessione Frontend:** All'accesso con sessione attiva, la navbar deve visualizzare username e ruolo, mentre al logout deve reindirizzare a `/oauth2/sign_out`.

---

### Task 1: Backend Model, Decoratore `@require_auth` ed Endpoint `/api/me`

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/app.py`
- Create: `tests/backend/test_forward_auth.py`

**Interfaces:**
- Consumes: Header HTTP `X-Forwarded-Email`, `X-Forwarded-Preferred-Username`, `X-Forwarded-Groups`.
- Produces: Modello `User` con `password_hash` opzionale, decoratore `@require_auth`, endpoint `GET /api/me`.

- [ ] **Step 1: Scrivere il test per `/api/me`, auto-provisioning e `@require_auth` in `tests/backend/test_forward_auth.py`**
  ```python
  def test_api_me_unauthenticated_production(client):
      res = client.get('/api/me')
      assert res.status_code == 401
      assert res.get_json()['authenticated'] is False

  def test_api_me_auto_provisioning_standard_user(client):
      headers = {
          'X-Forwarded-Email': 'alice@company.com',
          'X-Forwarded-Preferred-Username': 'alice'
      }
      res = client.get('/api/me', headers=headers)
      assert res.status_code == 200
      data = res.get_json()
      assert data['authenticated'] is True
      assert data['email'] == 'alice@company.com'
      assert data['role'] == 'User'

  def test_api_me_role_mapping_admin(client):
      headers = {
          'X-Forwarded-Email': 'bob@company.com',
          'X-Forwarded-Preferred-Username': 'bob',
          'X-Forwarded-Groups': 'erp-admins,staff'
      }
      res = client.get('/api/me', headers=headers)
      assert res.status_code == 200
      assert res.get_json()['role'] == 'Admin'
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_forward_auth.py -v`
  - Expected: FAIL (404 / endpoint not defined).

- [ ] **Step 3: Aggiornare `backend/models.py` e implementare `/api/me` e `@require_auth` in `backend/app.py`**
  - In `models.py`: impostare `password_hash = db.Column(db.String(128), nullable=True)` e aggiungere `oauth_provider = db.Column(db.String(50), default='oidc', nullable=True)`.
  - In `app.py`: definire `@require_auth(roles=None)` e `@app.route('/api/me', methods=['GET'])` conforme alla specifica.
  - Applicare `@require_auth(roles=['Admin'])` a `/api/users` (operazioni di modifica/cancellazione) e `/api/db-explorer`.

- [ ] **Step 4: Eseguire i test backend per verificare che passino (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/ -v`
  - Expected: Tutti i test passano (test_api.py + test_forward_auth.py).

---

### Task 2: Frontend Integration - Gestione Sessione `/api/me` e Flussi SSO

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/components/Auth.vue`
- Modify: `frontend/src/router.js`
- Create: `tests/frontend/AuthForward.spec.js`

**Interfaces:**
- Consumes: Risposta JSON di `GET /api/me`.
- Produces: Rendering dinamico del profilo utente autenticato, pulsante "Accedi con SSO" verso `/oauth2/start?rd=/dashboard`, logout verso `/oauth2/sign_out?rd=/`.

- [ ] **Step 1: Scrivere il test frontend in `tests/frontend/AuthForward.spec.js`**
  - Verificare che se `/api/me` restituisce utente non autenticato, venga mostrato il pulsante SSO.
  - Verificare che il link di logout punti a `/oauth2/sign_out?rd=/`.

- [ ] **Step 2: Eseguire il test per verificare il fallimento iniziale (RED)**
  - Run: `npm --prefix frontend run test tests/frontend/AuthForward.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Implementare l'integrazione `/api/me` e SSO in `Auth.vue` e `App.vue`**
  - In `Auth.vue`: aggiungere opzione/pulsante "Accedi con SSO / OIDC" che reindirizza a `/oauth2/start?rd=/dashboard`.
  - In `App.vue`: verificare la sessione con `/api/me` al mounted; impostare l'azione di logout su `window.location.href = '/oauth2/sign_out?rd=/'`.

- [ ] **Step 4: Eseguire la suite di test frontend (GREEN)**
  - Run: `npm --prefix frontend run test`
  - Expected: Tutti i test passano.

---

### Task 3: Infrastruttura Docker - Traefik v3 e oauth2-proxy

**Files:**
- Modify: `docker-compose.prod.yaml`
- Modify: `.env.prod`
- Modify: `proxy/nginx.conf`

**Interfaces:**
- Consumes: Configurazione container e variabili d'ambiente OIDC.
- Produces: Servizi `traefik`, `oauth2-proxy`, `frontend` (Nginx statico), `backend` orchestrati con labels di routing e middleware ForwardAuth.

- [ ] **Step 1: Aggiornare `proxy/nginx.conf`**
  - Rimuovere la direttiva `proxy_pass http://backend:8000;` da `nginx.conf`: il container Nginx frontend si occuperà esclusivamente di servire i file statici della SPA (`/usr/share/nginx/html`). Il routing di `/api` è gestito direttamente da Traefik.

- [ ] **Step 2: Configurare `docker-compose.prod.yaml`**
  - Aggiungere il servizio `traefik:v3.1` su porte 80 e 443 con labels per router e middleware.
  - Aggiungere il servizio `oauth2-proxy:v7.6.0` collegato a `traefik` e configurato con le variabili d'ambiente OIDC.
  - Assegnare le etichette `traefik.http.routers.frontend` e `traefik.http.routers.backend` per instradare `/` e `/api` con middleware `ForwardAuth`.

- [ ] **Step 3: Aggiornare `.env.prod`**
  - Inserire le variabili template necessarie per Traefik e oauth2-proxy (`OAUTH2_PROXY_*`, `TRAEFIK_DOMAIN`, `ACME_EMAIL`).

- [ ] **Step 4: Validare la configurazione Docker Compose**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.prod.yaml config`
  - Expected: Configurazione valida, exit code 0.

---

### Task 4: Verifica Completa ed Esecuzione Test Suite

**Files:**
- Tutti i file del progetto

- [ ] **Step 1: Eseguire tutti i test backend**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend -v`
  - Expected: 100% test superati.

- [ ] **Step 2: Eseguire tutti i test frontend**
  - Run: `npm --prefix frontend run test`
  - Expected: 100% test superati.

- [ ] **Step 3: Validare build del frontend**
  - Run: `npm --prefix frontend run build`
  - Expected: Build Vite completata con successo.

---

### Task 5: Commit Git Firmato GPG

**Files:**
- Repository Git

- [ ] **Step 1: Staging chirurgico dei file modificati**
  ```bash
  git add backend/ frontend/ proxy/ tests/ docker-compose.prod.yaml .env.prod docs/superpowers/plans/
  ```

- [ ] **Step 2: Commit firmato GPG**
  ```bash
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: integrazione oauth2-proxy, traefik v3 forwardauth e auto-provisioning"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Commit firmato valido con `gabbo <gabbo9lli@gmail.com>`.
