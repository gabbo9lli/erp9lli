# Catalogo EventType, Code Multiple con Redis Queue (RQ) e Policy Sincrono/Asincrono Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare il catalogo degli eventi registrabili (`EventType`) con policy configurabile sincrono/asincrono, routing su code multiple nominate con Redis Queue (`rq`) (`critical`, `emails`, `batch`, `default`), monitoraggio statistiche code e console Quasar in `ActivityCenter.vue`.

**Architecture:** Modello relazionale `EventType` e campi `event_type_id`, `coda_nome`, `rq_job_id` su `SystemEvent`. Integrazione di `rq` collegato a Redis su porta 6379 con routing su code dedicate. Endpoint REST per gestione catalogo eventi e statistiche code. Interfaccia Quasar per configurazione dinamica delle policy.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, RQ (Redis Queue), Redis 7, Alembic, PostgreSQL 15, Vue 3, Quasar 2.16, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-event-types-redis-multiple-queues-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Code Multiple RQ:** Supporto alle 4 code standard: `'critical'`, `'emails'`, `'batch'`, `'default'`.
- **Policy Dichiarativa:** Se `event_type.modalita_esecuzione == 'asincrono'`, il task deve essere automaticamente eseguito in background e restituire `202 Accepted`; se `'sincrono'`, eseguito immediatamente con risposta `201 Created`.
- **Stato 'test':** In ambiente di sviluppo/test (`SMTP_ENABLED != 'true'`), le comunicazioni esterne devono assumere lo stato **`test`** tracciate su DB senza connessioni esterne.

## Review Focus

1. **Persistenza e Relazioni `EventType`:** Creazione e collegamento con `EventChannel` ed `EventCategory`.
2. **Seed Eventi Chiave di ReteBio:** Popolamento automatico di `EMISSIONE_DDT`, `CONFERMA_ORDINE`, `CARICO_MERCI`, `INCASSO_RATA`, `EMISSIONE_FATTURA`, `SOLLECITO_PALLET`, `SOLLECITO_MASSIVO_PALLET`.
3. **Routing Automatico della Coda:** Verifica che un evento asincrono con `coda_nome='emails'` venga instradato sulla coda `emails`.
4. **Modifica Dinamica della Policy:** Endpoint `PUT /api/events/types/<id>` aggiorna la modalità di esecuzione senza riavvio del server.
5. **Statistiche Code Redis:** L'endpoint `/api/events/queues` restituisce lo stato delle 4 code.

---

### Task 1: Dipendenza `rq`, Modello `EventType`, Estensione `SystemEvent` e Migrazione Database

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/models/event_type.py`
- Modify: `backend/models/system_event.py`
- Modify: `backend/models/__init__.py`
- Create: `tests/backend/test_event_types_queues.py`

**Interfaces:**
- Produces: Modello `EventType`, campi `event_type_id`, `coda_nome`, `rq_job_id` su `SystemEvent`.

- [ ] **Step 1: Scrivere test per la persistenza di `EventType` in `tests/backend/test_event_types_queues.py`**
  ```python
  def test_event_type_model_persistence(client):
      from models import db, EventChannel, EventCategory, EventType, SystemEvent
      with client.application.app_context():
          ch = EventChannel(codice="EMAIL", nome="Email", tipo_dispatcher="smtp", richiede_destinatario=True)
          cat = EventCategory(codice="PALLET", nome="Pallet", colore_badge="deep-orange")
          db.session.add_all([ch, cat])
          db.session.commit()

          etype = EventType(
              codice="SOLLECITO_PALLET",
              nome="Sollecito Restituzione Pallet",
              channel_id=ch.id,
              category_id=cat.id,
              modalita_esecuzione="asincrono",
              coda_nome="emails"
          )
          db.session.add(etype)
          db.session.commit()

          assert etype.id is not None
          assert etype.modalita_esecuzione == "asincrono"
          assert etype.coda_nome == "emails"
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_event_types_queues.py -v`
  - Expected: FAIL (`ImportError: cannot import name 'EventType' from 'models'`).

- [ ] **Step 3: Aggiungere `rq` in `backend/requirements.txt`, creare `backend/models/event_type.py`, estendere `backend/models/system_event.py` e aggiornare `backend/models/__init__.py`**
  - Implementare modello `EventType` con campi e `to_dict()`.
  - Aggiungere colonne `event_type_id`, `coda_nome`, `rq_job_id` su `SystemEvent`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_event_types_queues.py -v`
  - Expected: PASS.

- [ ] **Step 5: Eseguire la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add event type catalog and rq fields" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Tabella `event_type` creata e colonne aggiunte a `system_event` su PostgreSQL.

---

### Task 2: Dispatcher con Routing Dinamico su Code Multiple Redis (`rq`)

**Files:**
- Modify: `backend/services/event_dispatcher.py`
- Modify: `tests/backend/test_event_types_queues.py`

**Interfaces:**
- Consumes: Redis su porta 6379, catalogo `EventType`.
- Produces: `dispatch_event` con lookup `event_type_code` e code `critical`, `emails`, `batch`, `default`.

- [ ] **Step 1: Scrivere test per il routing dichiarativo in `tests/backend/test_event_types_queues.py`**
  - `test_dispatch_event_declarative_async_from_event_type`: verifica che un evento con `modalita_esecuzione='asincrono'` e `coda_nome='emails'` venga instradato automaticamente come asincrono con `coda_nome='emails'`.
  - `test_dispatch_event_declarative_sync_from_event_type`: verifica che un evento con `modalita_esecuzione='sincrono'` venga eseguito immediatamente.

- [ ] **Step 2: Eseguire test per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_event_types_queues.py -v`
  - Expected: FAIL.

- [ ] **Step 3: Implementare seed `seed_default_event_types()` e routing su code in `backend/services/event_dispatcher.py`**
  - Lookup automatico da `EventType`.
  - Instradamento su `coda_nome`.

- [ ] **Step 4: Eseguire test (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_event_types_queues.py -v`
  - Expected: PASS (100%).

---

### Task 3: Backend REST APIs `EventType`, Policy Update e Statistiche Code Redis

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_event_types_queues.py`

**Interfaces:**
- Consumes: Header auth, modifiche policy.
- Produces: `GET /api/events/types`, `POST /api/events/types`, `PUT /api/events/types/<id>`, `GET /api/events/queues`.

- [ ] **Step 1: Scrivere test API in `tests/backend/test_event_types_queues.py`**
  - `test_api_event_types_crud_and_policy_update`: test recupero catalogo e cambio policy via PUT da sincrono ad asincrono.
  - `test_api_redis_queues_stats`: verifica endpoint statistiche code.

- [ ] **Step 2: Eseguire test per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_event_types_queues.py -v`
  - Expected: FAIL (404 Not Found).

- [ ] **Step 3: Implementare gli endpoint in `backend/app.py`**
  - Esporre le route `/api/events/types` e `/api/events/queues`.

- [ ] **Step 4: Eseguire tutti i test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_event_types_queues.py -v`
  - Expected: PASS (100%).

---

### Task 4: Frontend Quasar in `ActivityCenter.vue` per Catalogo Eventi e Code Redis

**Files:**
- Modify: `frontend/src/components/ActivityCenter.vue`
- Modify: `tests/frontend/ActivityCenter.spec.js`

**Interfaces:**
- Consumes: `/api/events/types`, `/api/events/queues`.
- Produces: Scheda "Catalogo Eventi & Code Redis" con modifica al volo delle policy sincrono/asincrono e monitor code.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/ActivityCenter.spec.js`**
  - Verifica rendering scheda catalogo eventi e widget contatori code Redis.

- [ ] **Step 2: Eseguire test per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/ActivityCenter.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Aggiornare `frontend/src/components/ActivityCenter.vue`**
  - Aggiungere scheda 5: "Catalogo Eventi & Code".
  - Widget contatori job code Redis in cima alla scheda.
  - Tabella eventi registrabili con selettori `modalita_esecuzione` e `coda_nome`.
  - Salvataggio modifiche policy con `PUT /api/events/types/<id>`.

- [ ] **Step 4: Eseguire test frontend (GREEN)**
  - Run: `npm --prefix frontend run test`
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

- [ ] **Step 4: Test live E2E nel container**
  - Modificare live una policy via curl da sincrono ad asincrono, verificare esecuzione su coda dedicata e statistiche `/api/events/queues`.

---

### Task 6: Commit Git Firmato GPG

**Files:**
- Repository Git

- [ ] **Step 1: Staging chirurgico dei file modificati**
  ```bash
  git add backend/ frontend/ tests/ docs/superpowers/plans/
  ```

- [ ] **Step 2: Commit firmato GPG**
  ```bash
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo catalogo event types code multiple redis queue e policy sincrono asincrono"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
