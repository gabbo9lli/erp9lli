# Architettura Modulare a Pacchetti e Modulo Ordini Clienti Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introdurre il framework di modularità a pacchetti (`ENABLED_MODULES`) con endpoint `GET /api/modules` e navigazione dinamica, e implementare il Modulo Supply Chain 1 (Ciclo Ordini Clienti `CustomerOrder`, `OrderItem` con sequenze a passi di 5, calcolo residui ed evasione diretta in Bolle DDT).

**Architecture:** Modelli relazionali `CustomerOrder` e `OrderItem` disaccoppiati in `backend/models/`. Parametrizzazione da environment variable `ENABLED_MODULES` (`all` o lista separata da virgole). Endpoint backend REST per ordini ed evasione transazionale in DDT. Componente Quasar `Orders.vue` con avanzamento percentuale e navigazione sidebar dinamica filtrata in base ai moduli attivi.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, Alembic, PostgreSQL 15, Vue 3, Quasar 2.16, Vite, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-20-modulo-ordini-e-architettura-modulare-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Sequenze Intercalate:** Le righe d'ordine devono essere assegnate con numerazione automatica a passi di 5 (`5, 10, 15, 20...`) per consentire intercalazioni.
- **Calcolo Residuo & Chiusura Automatica:** La quantità residua è `max(0, quantita_ordinata - quantita_consegnata)`. Una riga e l'ordine si chiudono automaticamente quando `quantita_consegnata >= quantita_ordinata`.

## Review Focus

1. **Endpoint Moduli Attivi:** `GET /api/modules` deve riflettere fedelmente la variabile `ENABLED_MODULES` (se `all`, tutti `true`).
2. **Reattività Sidebar Quasar:** La sidebar deve visualizzare solo le voci dei moduli attivi (`v-if="modules.orders"`, `v-if="modules.accounting"`, etc.).
3. **Numerazione Progressiva Annuale Ordine:** Creazione progressivo univoco `ORD-YYYY-XXXX` per ciascun anno solare.
4. **Evasione Parziale vs Totale:** All'evasione in DDT, se la merce consegnata è inferiore all'ordinato, lo stato dell'ordine deve diventare `'in_preparazione'`; se a saldo, `'chiuso'`.
5. **Integrità DDT Generato da Ordine:** Il DDT prodotto dall'evasione deve contenere cliente, righe merci e prezzi concordati nell'ordine.

---

### Task 1: Framework Modularità `ENABLED_MODULES`, Endpoint `GET /api/modules` e Sidebar Dinamica

**Files:**
- Modify: `backend/app.py`
- Modify: `frontend/src/App.vue`
- Create: `tests/backend/test_orders_and_modules.py`

**Interfaces:**
- Produces: Endpoint `GET /api/modules` che restituisce `{"anagrafiche": true, "orders": true, "delivery_notes": true, "invoicing": true, "accounting": true}`.

- [ ] **Step 1: Scrivere test per `GET /api/modules` in `tests/backend/test_orders_and_modules.py`**
  ```python
  def test_get_modules_endpoint(client):
      res = client.get('/api/modules')
      assert res.status_code == 200
      data = res.get_json()
      assert "anagrafiche" in data
      assert "orders" in data
      assert "delivery_notes" in data
      assert "invoicing" in data
      assert "accounting" in data
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_orders_and_modules.py -v`
  - Expected: FAIL (404 / endpoint non trovato).

- [ ] **Step 3: Implementare `is_module_enabled` e `GET /api/modules` in `backend/app.py`**
  - Leggere `ENABLED_MODULES` da `os.getenv('ENABLED_MODULES', 'all')`.
  - Definire `is_module_enabled(mod_name)` che supporta `'all'` o lista separata da virgole.
  - Implementare route `GET /api/modules`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_orders_and_modules.py -v`
  - Expected: PASS.

- [ ] **Step 5: Aggiornare `frontend/src/App.vue` per filtrare la Sidebar in base ai moduli attivi**
  - In `App.vue`: stato reattivo `activeModules`, fetch di `/api/modules` all'avvio.
  - Aggiungere `v-if="activeModules.orders"`, `v-if="activeModules.delivery_notes"`, `v-if="activeModules.invoicing"`, `v-if="activeModules.accounting"`, `v-if="activeModules.anagrafiche"`.

---

### Task 2: Modelli `CustomerOrder` & `OrderItem` e Migrazione Database

**Files:**
- Create: `backend/models/customer_order.py`
- Create: `backend/models/order_item.py`
- Modify: `backend/models/__init__.py`
- Modify: `tests/backend/test_orders_and_modules.py`

**Interfaces:**
- Produces: Classi SQLAlchemy `CustomerOrder` e `OrderItem` con calcolo proprietà `quantita_residua`.

- [ ] **Step 1: Scrivere test per la persistenza dei modelli ordine in `tests/backend/test_orders_and_modules.py`**
  ```python
  def test_order_model_persistence_and_residual(client):
      from models import db, Partner, Product, CustomerOrder, OrderItem
      from datetime import date
      with client.application.app_context():
          p = Partner(ragione_sociale="Cliente Ordine Test", tipo="cliente")
          prod = Product(codice="ART-ORD-1", descrizione="Mele Bio", prezzo_vendita=2.5)
          db.session.add_all([p, prod])
          db.session.commit()

          order = CustomerOrder(
              numero=1,
              anno=2026,
              numero_completo="ORD-2026-0001",
              data_ordine=date.today(),
              cliente_id=p.id,
              stato="aperto"
          )
          db.session.add(order)
          db.session.commit()

          item = OrderItem(
              order_id=order.id,
              product_id=prod.id,
              sequenza=5,
              descrizione=prod.descrizione,
              colli_ordinati=10,
              quantita_ordinata=100.0,
              colli_consegnati=4,
              quantita_consegnata=40.0,
              prezzo_unitario=2.5
          )
          db.session.add(item)
          db.session.commit()

          assert order.id is not None
          assert len(order.items) == 1
          assert item.quantita_residua == 60.0
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_orders_and_modules.py -v`
  - Expected: FAIL (`ImportError: cannot import name 'CustomerOrder' from 'models'`).

- [ ] **Step 3: Creare `backend/models/customer_order.py`, `backend/models/order_item.py` e aggiornare `backend/models/__init__.py`**
  - Implementare classi e metodi `to_dict()`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_orders_and_modules.py -v`
  - Expected: PASS.

- [ ] **Step 5: Eseguire la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add customer order models" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Tabelle `customer_order` e `order_item` create con successo su PostgreSQL.

---

### Task 3: Backend REST APIs Ordini ed Evasione in DDT (`/api/orders/...`)

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_orders_and_modules.py`

**Interfaces:**
- Consumes: Header auth, ordini con righe, richieste di evasione DDT.
- Produces: Endpoint `/api/orders`, `/api/orders/<id>`, `/api/orders/<id>/fulfill-to-ddt`.

- [ ] **Step 1: Scrivere test API ordini ed evasione in `tests/backend/test_orders_and_modules.py`**
  - `test_create_order_with_step5_sequences`: creazione ordine, verifica progressivo `ORD-YYYY-XXXX` e sequenze 5, 10, 15...
  - `test_order_partial_fulfillment_to_ddt`: evasione parziale di 40 Kg su 100 Kg; creazione DDT, aggiornamento `quantita_consegnata=40`, residuo 60 Kg, stato ordine `'in_preparazione'`.
  - `test_order_full_fulfillment_closes_order`: evasione dei residui restanti; verifica passaggio automatico dell'ordine a stato `'chiuso'`.

- [ ] **Step 2: Eseguire test API per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_orders_and_modules.py -v`
  - Expected: FAIL (404 / endpoints not found).

- [ ] **Step 3: Implementare gli endpoint ordini in `backend/app.py`**
  - Helper `get_next_order_number(anno)`.
  - Endpoint `GET /api/orders` e `GET /api/orders/<int:oid>`.
  - Endpoint `POST /api/orders`: numerazione a passi di 5 (5, 10, 15...).
  - Endpoint `PUT /api/orders/<int:oid>`.
  - Endpoint `POST /api/orders/<int:oid>/fulfill-to-ddt`: generazione bolla DDT con righe merce, aggiornamento quantità evase e chiusura automatica ordine/righe se saldo raggiunto.

- [ ] **Step 4: Eseguire tutti i test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/ -v`
  - Expected: 100% test superati.

---

### Task 4: Frontend Component `Orders.vue` e Routing

**Files:**
- Create: `frontend/src/components/Orders.vue`
- Modify: `frontend/src/router.js`
- Create: `tests/frontend/Orders.spec.js`

**Interfaces:**
- Consumes: `/api/orders`, `/api/partners`, `/api/products`.
- Produces: Maschera Quasar con avanzamento percentuale, dialog nuovo ordine e wizard evasione rapida in DDT.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/Orders.spec.js`**
  - Verifica caricamento lista ordini, badge di stato e pulsante di evasione DDT.

- [ ] **Step 2: Eseguire test frontend per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/Orders.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Creare `frontend/src/components/Orders.vue`**
  - Tabella `<q-table>` ordini con colonna avanzamento (barra di progresso percentuale consegnato/ordinato).
  - Dialog nuovo ordine con sequenze a passi di 5 e selezione prodotti.
  - Dialog / wizard di evasione in DDT con selezione quantità da consegnare.

- [ ] **Step 4: Aggiornare `frontend/src/router.js`**
  - Aggiungere rotta protetta `/orders` con meta per modulo `orders`.

- [ ] **Step 5: Eseguire tutti i test frontend (GREEN)**
  - Run: `npm --prefix frontend run test`
  - Expected: 100% test superati.

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
  - Creare ordine live via curl, verificare sequenze e procedere con evasione parziale in DDT.

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
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: architettura modulare a pacchetti e modulo ordini clienti con evasione ddt"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
