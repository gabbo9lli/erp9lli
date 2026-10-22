# Event Bus, Audit Trail, Canali Estendibili e Coda Task in Background Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare la dorsale architetturale per Event Bus, Audit Trail delle attività utente, Canali estendibili (`EventChannel`), Categorie strutturate (`EventCategory`), Coda di Background per task asincroni a lunga durata (Job Queue con risposta HTTP 202 e progresso 0-100%), Dispatcher con gestione ambienti (stato `'test'` in dev vs invio reale in prod) e console Quasar `ActivityCenter.vue`.

**Architecture:** Modelli relazionali `EventChannel`, `EventCategory` e `SystemEvent`. Modulo di dispacciamento `backend/services/event_dispatcher.py` basato su `ThreadPoolExecutor` con tracking percentuale ed emissione Socket.IO. Endpoint REST per eventi, retry e batch solleciti pallet. Console Quasar a 4 schede e pulsante batch in `Pallets.vue`.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, Alembic, PostgreSQL 15, ThreadPoolExecutor, Flask-SocketIO, Vue 3, Quasar 2.16, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-event-bus-background-queue-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Stato 'test':** In ambiente di sviluppo/test (`SMTP_ENABLED != 'true'`), le comunicazioni esterne devono assumere lo stato **`test`** (non `simulato_test`), restando tracciate su DB senza connessioni esterne.
- **Risposta Asincrona HTTP 202:** I task con `is_async=True` restituiscono immediatamente `202 Accepted` con `task_id` e progresso iniziale a `0`.
- **Canali Estendibili:** I canali fanno capo all'anagrafica relazionale `EventChannel` (`tipo_dispatcher`: `internal`, `smtp`, `webhook`).

## Review Focus

1. **Seed Canali e Categorie Base:** Inizializzazione automatica dei canali `AUDIT`, `EMAIL`, `PEC`, `WEBHOOK` e categorie di sistema.
2. **Esecuzione Sincrona Audit:** Scrittura immediata di eventi `AUDIT` con `stato = 'completato'` e `progresso = 100`.
3. **Dispatch Email in Modalità Test:** Salvataggio con `stato = 'test'` senza eccezioni di rete quando non configurato SMTP.
4. **Coda Asincrona in Background:** Esecuzione del job in thread separato con avanzamento `progresso: 0 -> 100%`.
5. **Batch Solleciti Pallet Asincrono:** L'endpoint `/api/pallets/batch-solleciti` crea il task in background e risponde 202.

---

### Task 1: Modelli Relazionali `EventChannel`, `EventCategory`, `SystemEvent` e Migrazione Database

**Files:**
- Create: `backend/models/event_channel.py`
- Create: `backend/models/event_category.py`
- Create: `backend/models/system_event.py`
- Modify: `backend/models/__init__.py`
- Create: `tests/backend/test_event_bus.py`

**Interfaces:**
- Produces: Classi SQLAlchemy `EventChannel`, `EventCategory`, `SystemEvent`.

- [ ] **Step 1: Scrivere test per la persistenza dei modelli in `tests/backend/test_event_bus.py`**
  ```python
  def test_event_models_persistence(client):
      from models import db, EventChannel, EventCategory, SystemEvent
      with client.application.app_context():
          ch = EventChannel(codice="AUDIT", nome="Audit Log", tipo_dispatcher="internal")
          cat = EventCategory(codice="LOGISTICA", nome="Logistica & Magazzino", colore_badge="teal")
          db.session.add_all([ch, cat])
          db.session.commit()

          event = SystemEvent(
              channel_id=ch.id,
              category_id=cat.id,
              azione="emissione_ddt",
              titolo="Emesso DDT-2026-0001",
              descrizione="Consegna merci completata",
              stato="completato",
              progresso=100
          )
          db.session.add(event)
          db.session.commit()

          assert event.id is not None
          assert event.channel.codice == "AUDIT"
          assert event.category.codice == "LOGISTICA"
          assert event.stato == "completato"
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_event_bus.py -v`
  - Expected: FAIL (`ImportError: cannot import name 'EventChannel' from 'models'`).

- [ ] **Step 3: Creare `backend/models/event_channel.py`, `backend/models/event_category.py`, `backend/models/system_event.py` e aggiornare `backend/models/__init__.py`**
  - Implementare modelli con relazioni e metodi `to_dict()`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_event_bus.py -v`
  - Expected: PASS.

- [ ] **Step 5: Eseguire la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add event bus channels and system events" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Tabelle `event_channel`, `event_category` e `system_event` create su PostgreSQL.

---

### Task 2: Backend Service `event_dispatcher.py` con Esecuzione Sincrona, Asincrona e Canali

**Files:**
- Create: `backend/services/event_dispatcher.py`
- Modify: `tests/backend/test_event_bus.py`

**Interfaces:**
- Produces: `dispatch_event(...)` e `seed_default_channels_and_categories()`.

- [ ] **Step 1: Scrivere test per il dispatcher in `tests/backend/test_event_bus.py`**
  - `test_dispatch_audit_event_synchronous`: verifica scrittura sincrona con `stato='completato'` e `progresso=100`.
  - `test_dispatch_email_in_test_environment`: verifica che sul canale `EMAIL` assuma `stato='test'` senza chiamate esterne.
  - `test_background_async_task_progress`: verifica esecuzione in thread worker con incremento progresso `0 -> 100%` e completamento.

- [ ] **Step 2: Eseguire test per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_event_bus.py -v`
  - Expected: FAIL (`ModuleNotFoundError: No module named 'services.event_dispatcher'`).

- [ ] **Step 3: Implementare `backend/services/event_dispatcher.py`**
  - Implementare `seed_default_channels_and_categories()`.
  - Implementare `dispatch_event(...)` con supporto `ThreadPoolExecutor` per `is_async=True`.

- [ ] **Step 4: Eseguire test (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_event_bus.py -v`
  - Expected: PASS (100%).

---

### Task 3: Backend REST APIs Eventi, Coda Task, Canali e Batch Solleciti Pallet

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_event_bus.py`

**Interfaces:**
- Consumes: Header auth, filtri eventi, richieste di dispatching.
- Produces: `GET /api/events`, `GET /api/events/<id>`, `POST /api/events`, `GET /api/events/channels`, `GET /api/events/categories`, `POST /api/events/<id>/retry`, `POST /api/pallets/batch-solleciti`.

- [ ] **Step 1: Scrivere test API in `tests/backend/test_event_bus.py`**
  - `test_api_events_crud_and_channels`: consultazione canali ed eventi.
  - `test_api_async_event_returns_202`: verifica risposta HTTP 202 con `task_id` e `progresso`.
  - `test_api_pallet_batch_solleciti_background`: verifica avvio batch solleciti pallet asincrono.

- [ ] **Step 2: Eseguire test per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_event_bus.py -v`
  - Expected: FAIL (404 Not Found).

- [ ] **Step 3: Implementare gli endpoint in `backend/app.py`**
  - Esporre le route `/api/events/...` e `/api/pallets/batch-solleciti`.

- [ ] **Step 4: Eseguire tutti i test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/ -v`
  - Expected: PASS (100%).

---

### Task 4: Frontend Quasar `ActivityCenter.vue`, Integrazione Solleciti in `Pallets.vue` e Routing

**Files:**
- Create: `frontend/src/components/ActivityCenter.vue`
- Modify: `frontend/src/components/Pallets.vue`
- Modify: `frontend/src/router.js`
- Modify: `frontend/src/App.vue`
- Create: `tests/frontend/ActivityCenter.spec.js`

**Interfaces:**
- Consumes: `/api/events`, `/api/events/channels`, `/api/pallets/batch-solleciti`.
- Produces: Console Quasar a 4 schede con progress bar dei task in background e pulsanti di sollecito in `Pallets.vue`.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/ActivityCenter.spec.js`**
  - Verifica caricamento schede, timeline audit trail e visualizzazione stato `'test'`.

- [ ] **Step 2: Eseguire test per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/ActivityCenter.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Creare `frontend/src/components/ActivityCenter.vue`**
  - Tab 1: Audit Trail timeline.
  - Tab 2: Coda Task in background con `q-linear-progress`.
  - Tab 3: Comunicazioni Outbox (chip verde *Completato* vs azzurro *Test*).
  - Tab 4: Anagrafica Canali.

- [ ] **Step 4: Aggiornare `frontend/src/components/Pallets.vue`**
  - Aggiungere pulsante *"Sollecito"* per singolo buono e pulsante *"Invia Solleciti Massivi"* in testata.

- [ ] **Step 5: Aggiornare `frontend/src/router.js` e `frontend/src/App.vue`**
  - Rotta `/activities` e link sidebar sotto Amministrazione & Sistema.

- [ ] **Step 6: Eseguire test frontend (GREEN)**
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
  - Invocare live un task asincrono via curl, verificare risposta 202, avanzamento e stato finale `'test'`.

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
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo event bus audit trail canali estendibili e coda task background"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
