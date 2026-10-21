# Entrata Merci da Fornitori e Giacenze Magazzino FEFO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare il modulo Supply Chain 2 (`warehouse`): Entrata Merci da Fornitori (`PurchaseDeliveryNote`, `PurchaseDeliveryNoteItem`), Cruscotto Giacenze per Lotto in tempo reale, e Motore di Suggerimento FEFO (First Expired, First Out) per l'emissione dei DDT di vendita.

**Architecture:** Modelli relazionali in `backend/models/`. Calcolo algebrico giacenze per lotto ($\sum \text{Carichi Fornitori} - \sum \text{Scarichi DDT Vendita}$). Logica FEFO per estrarre prioritariamente i lotti con data di scadenza più prossima. Componenti Quasar `Purchases.vue` e `WarehouseStock.vue`, integrazione pulsante FEFO in `DeliveryNotes.vue`, e disaccoppiamento governato da `ENABLED_MODULES` (`warehouse`).

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, Alembic, PostgreSQL 15, Vue 3, Quasar 2.16, Vite, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-20-entrata-merci-giacenze-fefo-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Tracciabilità Biologica di Carico:** Nei prodotti con `in_scadenza == True`, le righe carico fornitore impongono obbligatoriamente `lotto` e `data_scadenza` (errore 400 se mancanti).
- **Logica FEFO:** L'ordinamento dei lotti suggeriti per la vendita DEVE essere rigorosamente `data_scadenza ASC, data_ricezione ASC`.

## Review Focus

1. **Validazione Lotti su Carichi:** Rifiuto (400) se un carico fornitore include prodotti deperibili senza lotto o senza data di scadenza.
2. **Quadratura Giacenza per Lotto:** Sottrazione esatta tra carichi acquisto e scarichi DDT vendita per ciascun lotto (`carichi - scarichi`).
3. **Priorità FEFO Corretta:** Dati due lotti disponibili, il suggerimento FEFO deve proporre in cima quello con scadenza più ravvicinata.
4. **Disaccoppiamento Modulare:** L'emissione di DDT di vendita deve funzionare regolarmente anche in assenza di carichi a magazzino.
5. **Reattività Sidebar e Navigation Guard:** Se il modulo `warehouse` è attivo, le voci *Entrata Merci* e *Giacenze Magazzino* compaiono nella sidebar sotto *Logistica & Magazzino*.

---

### Task 1: Modelli `PurchaseDeliveryNote` & `PurchaseDeliveryNoteItem` e Migrazione Database

**Files:**
- Create: `backend/models/purchase_delivery_note.py`
- Create: `backend/models/purchase_delivery_note_item.py`
- Modify: `backend/models/__init__.py`
- Create: `tests/backend/test_warehouse_fefo.py`

**Interfaces:**
- Produces: Classi SQLAlchemy `PurchaseDeliveryNote` e `PurchaseDeliveryNoteItem` con relazioni su `Partner` e `Product`.

- [ ] **Step 1: Scrivere test per la persistenza dei modelli carico fornitore in `tests/backend/test_warehouse_fefo.py`**
  ```python
  def test_purchase_delivery_note_model(client):
      from models import db, Partner, Product, PurchaseDeliveryNote, PurchaseDeliveryNoteItem
      from datetime import date
      with client.application.app_context():
          supplier = Partner(ragione_sociale="BioProduttori Romagna", tipo="fornitore")
          prod = Product(codice="ART-BIO-CARICO", descrizione="Pesche Bio", in_scadenza=True, prezzo_acquisto=1.2)
          db.session.add_all([supplier, prod])
          db.session.commit()

          pdn = PurchaseDeliveryNote(
              numero_documento_fornitore="DDT-998/F",
              data_documento=date.today(),
              data_ricezione=date.today(),
              fornitore_id=supplier.id,
              colli_totali=10,
              peso_totale_netto=100.0,
              totale_imponibile=120.0
          )
          db.session.add(pdn)
          db.session.commit()

          item = PurchaseDeliveryNoteItem(
              purchase_delivery_note_id=pdn.id,
              product_id=prod.id,
              descrizione=prod.descrizione,
              colli=10,
              quantita=100.0,
              prezzo_unitario=1.2,
              lotto="LOTTO-PESCA-2026",
              data_scadenza=date.today()
          )
          db.session.add(item)
          db.session.commit()

          assert pdn.id is not None
          assert len(pdn.items) == 1
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_warehouse_fefo.py -v`
  - Expected: FAIL (`ImportError: cannot import name 'PurchaseDeliveryNote' from 'models'`).

- [ ] **Step 3: Creare `backend/models/purchase_delivery_note.py`, `backend/models/purchase_delivery_note_item.py` e aggiornare `backend/models/__init__.py`**
  - Implementare modelli con metodi `to_dict()`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_warehouse_fefo.py -v`
  - Expected: PASS.

- [ ] **Step 5: Eseguire la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add purchase delivery note models" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Tabelle create con successo su PostgreSQL.

---

### Task 2: Backend REST APIs Entrata Merci, Giacenze Magazzino e Motore FEFO

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_warehouse_fefo.py`

**Interfaces:**
- Consumes: Carichi fornitori, scarichi vendite DDT.
- Produces: Endpoint `/api/purchases`, `/api/purchases/<id>`, `/api/warehouse/stock`, `/api/warehouse/fefo-suggestions`.

- [ ] **Step 1: Scrivere test API in `tests/backend/test_warehouse_fefo.py`**
  - `test_create_purchase_validation_lotto_bio`: se articolo in scadenza e manca lotto o scadenza, restituisce 400.
  - `test_stock_running_calculation`: carico fornitore 100 Kg LOTTO-A, scarico vendita DDT 30 Kg LOTTO-A -> giacenza risultante esattamente 70 Kg.
  - `test_fefo_suggestion_ordering`: carico LOTTO-1 (scadenza 10/11/2026) e LOTTO-2 (scadenza 25/11/2026) -> il suggerimento FEFO posiziona al primo posto LOTTO-1.

- [ ] **Step 2: Eseguire test API per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_warehouse_fefo.py -v`
  - Expected: FAIL (404 / endpoints not found).

- [ ] **Step 3: Implementare gli endpoint del magazzino in `backend/app.py`**
  - Includere `"warehouse"` in `AVAILABLE_MODULES`.
  - Endpoint `GET /api/purchases` e `GET /api/purchases/<int:pid>`.
  - Endpoint `POST /api/purchases` (registrazione carico e validazione obbligatorietà lotti per deperibili bio).
  - Endpoint `GET /api/warehouse/stock` (aggregazione carichi - scarichi per combinazione prodotto/lotto).
  - Endpoint `GET /api/warehouse/fefo-suggestions?product_id=X` (ordinamento `data_scadenza ASC`).

- [ ] **Step 4: Eseguire tutti i test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/ -v`
  - Expected: 100% test superati.

---

### Task 3: Integrazione Suggeritore FEFO in `DeliveryNotes.vue`

**Files:**
- Modify: `frontend/src/components/DeliveryNotes.vue`
- Modify: `tests/frontend/DeliveryNotes.spec.js`

**Interfaces:**
- Consumes: `/api/warehouse/fefo-suggestions`.
- Produces: Tasto o tendina selezione rapida lotto FEFO nella modale di compilazione riga DDT vendita.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/DeliveryNotes.spec.js`**
  - Verifica visualizzazione suggeritore lotto FEFO se articolo è deperibile bio.

- [ ] **Step 2: Eseguire test per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/DeliveryNotes.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Aggiornare `frontend/src/components/DeliveryNotes.vue`**
  - Al cambio prodotto nella dialog riga DDT, interrogare `/api/warehouse/fefo-suggestions?product_id=...`.
  - Se disponibili lotti FEFO, mostrare chip o pulsante con icona `auto_awesome` *"Consigliato FEFO: Lotto X (Scadenza Y, Giacenza Z Kg)"* con autocompilazione al click.

- [ ] **Step 4: Eseguire test frontend (GREEN)**
  - Run: `npm --prefix frontend run test ../tests/frontend/DeliveryNotes.spec.js`
  - Expected: PASS.

---

### Task 4: Frontend Components `Purchases.vue` e `WarehouseStock.vue` e Routing

**Files:**
- Create: `frontend/src/components/Purchases.vue`
- Create: `frontend/src/components/WarehouseStock.vue`
- Modify: `frontend/src/router.js`
- Modify: `frontend/src/App.vue`
- Create: `tests/frontend/WarehouseStock.spec.js`

**Interfaces:**
- Consumes: `/api/purchases`, `/api/warehouse/stock`.
- Produces: Maschere carichi fornitore e cruscotto scorte con semaforo scadenze.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/WarehouseStock.spec.js`**
  - Verifica caricamento cruscotto giacenze e rendering lotti bio.

- [ ] **Step 2: Eseguire test frontend per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/WarehouseStock.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Creare `frontend/src/components/Purchases.vue` e `WarehouseStock.vue`**
  - `Purchases.vue`: tabella bolle fornitore e dialog di registrazione carico.
  - `WarehouseStock.vue`: tabella scorte per articolo con espansione lotti e badge semaforici scadenze.

- [ ] **Step 4: Aggiornare `frontend/src/router.js` e `frontend/src/App.vue`**
  - Aggiungere rotte protette `/purchases` e `/warehouse`.
  - Aggiungere sezione *"Logistica & Magazzino"* nella sidebar di `App.vue` con `v-if="activeModules.warehouse"`.

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
  - Registrare carico fornitore via curl con lotto e scadenza.
  - Verificare stock in `/api/warehouse/stock` e suggerimento FEFO in `/api/warehouse/fefo-suggestions`.

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
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo entrata merci da fornitori e giacenze magazzino fefo"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
