# Connettore & Sincronizzazione E-Commerce (Spree Commerce API / Webhook Shop) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare il modulo di sincronizzazione e-commerce (`EcommerceService`) con ricezione webhook idempotente per ordini Spree Commerce, auto-provisioning clienti, sequenze righe ordine a step 5, feed real-time delle giacenze di magazzino, tracciamento `EcommerceSyncLog` e interfaccia Quasar in `Orders.vue`.

**Architecture:** Modello relazionale `EcommerceSyncLog` e campi `external_reference`, `canale_vendita` su `CustomerOrder`. Servizio `EcommerceService` per parsing tracciato Spree e calcolo stock feed. Endpoint REST `/api/ecommerce/webhook/orders` con autenticazione ibrida (RBAC o header `X-Ecommerce-Secret`) ed emissione evento `WEBHOOK` su Event Bus. Visualizzazione badge canale e dialog log in `Orders.vue`.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, Alembic, PostgreSQL 15, Vue 3, Quasar 2.16, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-sincronizzazione-ecommerce-spree-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Architettura Modulare:** Aggiungere `"ecommerce"` a `AVAILABLE_MODULES` in `backend/app.py`.
- **Idempotenza Assoluta:** Se un ordine con lo stesso `external_reference` viene ri-inviato, il sistema non crea duplicati e risponde HTTP 200 con l'ordine preesistente.
- **Sequenze Step 5:** Tutte le righe dell'ordine generato devono avere sequenza progressiva a passi di 5 (`5, 10, 15, 20...`).
- **Tracciamento Event Bus:** Ogni ordine importato deve emettere un evento su canale `WEBHOOK` e categoria `VENDITE`.

## Review Focus

1. **Persistenza e Relazioni E-Commerce:** Creazione tabella `ecommerce_sync_log` e colonne `external_reference`, `canale_vendita` su `customer_order`.
2. **Auto-provisioning Cliente:** Se il cliente dell'ordine e-commerce non esiste per email o codice, viene creato automaticamente come `Partner` di tipo `cliente`.
3. **Idempotenza Webhook:** Verifica che una seconda chiamata con stesso `number` restituisca 200 senza aggiungere ordini.
4. **Feed Giacenze Magazzino:** Endpoint `/api/ecommerce/sync/stock` calcola correttamente la disponibilità residua reale.
5. **Autenticazione Webhook Segreta:** Rifiuto richieste con secret errato e accettazione con secret valido.

---

### Task 1: Modello `EcommerceSyncLog`, Estensione `CustomerOrder` e Migrazione Database

**Files:**
- Create: `backend/models/ecommerce_sync_log.py`
- Modify: `backend/models/customer_order.py`
- Modify: `backend/models/__init__.py`
- Create: `tests/backend/test_ecommerce_sync.py`

**Interfaces:**
- Produces: Modello `EcommerceSyncLog`, colonne `external_reference`, `canale_vendita` su `CustomerOrder`.

- [ ] **Step 1: Scrivere test per la persistenza del modello `EcommerceSyncLog` in `tests/backend/test_ecommerce_sync.py`**
  ```python
  def test_ecommerce_sync_models_persistence(client):
      from models import db, CustomerOrder, EcommerceSyncLog, Partner
      with client.application.app_context():
          cli = Partner(ragione_sociale="Cliente Web", tipo="cliente")
          db.session.add(cli)
          db.session.commit()

          order = CustomerOrder(
              numero=1,
              anno=2026,
              numero_completo="ORD-2026-0001",
              cliente_id=cli.id,
              external_reference="SPREE-R999",
              canale_vendita="ecommerce"
          )
          db.session.add(order)
          db.session.commit()

          log = EcommerceSyncLog(
              tipo_operazione="import_order",
              external_order_id="SPREE-R999",
              customer_order_id=order.id,
              stato="success",
              payload_ricevuto={"number": "SPREE-R999", "total": 120.0}
          )
          db.session.add(log)
          db.session.commit()

          assert log.id is not None
          assert order.external_reference == "SPREE-R999"
          assert order.canale_vendita == "ecommerce"
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_ecommerce_sync.py -v`
  - Expected: FAIL (`ImportError: cannot import name 'EcommerceSyncLog' from 'models'`).

- [ ] **Step 3: Creare `backend/models/ecommerce_sync_log.py`, estendere `customer_order.py` e aggiornare `__init__.py`**
  - Implementare modello `EcommerceSyncLog` e colonne `external_reference`, `canale_vendita` su `CustomerOrder`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_ecommerce_sync.py -v`
  - Expected: PASS.

- [ ] **Step 5: Eseguire la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add ecommerce sync log and customer order external ref" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Tabella `ecommerce_sync_log` creata e colonne aggiunte su PostgreSQL.

---

### Task 2: Servizio Connettore `EcommerceService` (Import Idempotente e Feed Giacenze)

**Files:**
- Create: `backend/services/ecommerce_service.py`
- Modify: `tests/backend/test_ecommerce_sync.py`

**Interfaces:**
- Produces: `EcommerceService.process_incoming_order(payload) -> tuple[CustomerOrder, bool]`, `EcommerceService.get_stock_sync_feed() -> list[dict]`.

- [ ] **Step 1: Scrivere test per `EcommerceService` in `tests/backend/test_ecommerce_sync.py`**
  - `test_ecommerce_service_import_order_and_idempotency`: verifica importazione ordine Spree, sequenze step 5, creazione cliente e risposta idempotente su secondo invio.
  - `test_ecommerce_service_stock_sync_feed`: verifica calcolo giacenze catalogo per lo shop.

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_ecommerce_sync.py -k "test_ecommerce_service" -v`
  - Expected: FAIL (`ModuleNotFoundError: No module named 'services.ecommerce_service'`).

- [ ] **Step 3: Implementare `backend/services/ecommerce_service.py`**
  - Parsing formato Spree Commerce (`number`, `email`, `bill_address`, `line_items`).
  - Lookup o auto-creation `Partner`.
  - Generazione `CustomerOrder` e `OrderItem` a step 5.
  - Log in `EcommerceSyncLog`.
  - Calcolo `get_stock_sync_feed`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_ecommerce_sync.py -k "test_ecommerce_service" -v`
  - Expected: PASS.

---

### Task 3: Backend REST APIs Webhook E-Commerce, Sync Giacenze ed Event Bus

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_ecommerce_sync.py`

**Interfaces:**
- Produces: `POST /api/ecommerce/webhook/orders`, `GET /api/ecommerce/sync/stock`, `GET /api/ecommerce/logs`.

- [ ] **Step 1: Scrivere test API in `tests/backend/test_ecommerce_sync.py`**
  - `test_api_ecommerce_webhook_endpoint_auth_and_import`: ricezione webhook con autenticazione via secret, risposte 201 e 200 idempotente.
  - `test_api_ecommerce_stock_and_logs`: test endpoint `/api/ecommerce/sync/stock` e `/api/ecommerce/logs`.

- [ ] **Step 2: Eseguire i test per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_ecommerce_sync.py -k "test_api_ecommerce" -v`
  - Expected: FAIL (404 Not Found).

- [ ] **Step 3: Implementare gli endpoint e abilitare `"ecommerce"` in `AVAILABLE_MODULES` in `backend/app.py`**
  - Esporre le route e collegare `dispatch_event` con canale `WEBHOOK`.

- [ ] **Step 4: Eseguire tutti i test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_ecommerce_sync.py -v`
  - Expected: PASS (100%).

---

### Task 4: Frontend Quasar in `Orders.vue` per Canale E-Commerce e Dialog Sincronizzazione

**Files:**
- Modify: `frontend/src/components/Orders.vue`
- Modify: `tests/frontend/Orders.spec.js`

**Interfaces:**
- Consumes: `/api/orders`, `/api/ecommerce/logs`, `/api/ecommerce/sync/stock`.
- Produces: Badge canale `ECOMMERCE` e dialog visualizzazione log sincronizzazione.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/Orders.spec.js`**
  - Verifica rendering badge `ECOMMERCE` e riferimento esterno Spree nella tabella ordini.

- [ ] **Step 2: Eseguire test per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/Orders.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Aggiornare `frontend/src/components/Orders.vue`**
  - Badge canale vendita nella colonna numero ordine.
  - Pulsante e dialog "Sincronizzazione E-Commerce & Log Webhook" con tabella log e tasto download feed giacenze.

- [ ] **Step 4: Eseguire test frontend (GREEN)**
  - Run: `npm --prefix frontend run test ../tests/frontend/Orders.spec.js`
  - Expected: PASS (100%).

---

### Task 5: Verifica Completa ed Esecuzione Test Suite

**Files:**
- Tutti i file del progetto

- [ ] **Step 1: Eseguire tutti i test backend**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend -v`
  - Expected: 100% test passano.

- [ ] **Step 2: Eseguire tutti i test frontend**
  - Run: `npm --prefix frontend run test`
  - Expected: 100% test passano.

- [ ] **Step 3: Validare build frontend**
  - Run: `npm --prefix frontend run build`
  - Expected: Build completata con successo.

- [ ] **Step 4: Test live E2E nel container Docker**
  - Invio ordine Spree via curl su `/api/ecommerce/webhook/orders`, verifica creazione ordine e log.

---

### Task 6: Finalizzazione e Commit Git Firmato GPG

**Files:**
- Repository Git

- [ ] **Step 1: Staging chirurgico dei file modificati**
  ```bash
  git add backend/ frontend/ tests/ docs/superpowers/plans/
  ```

- [ ] **Step 2: Commit firmato GPG**
  ```bash
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo connettore sincronizzazione ecommerce spree webhook ordini e sync stock"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
