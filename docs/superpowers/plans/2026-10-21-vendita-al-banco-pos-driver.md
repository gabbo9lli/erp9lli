# Vendita al Banco / Cassa Rapida (BancoM / POS) con Driver RT Pluggabile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare il modulo di Vendita al Banco e Cassa Rapida (`BancoM` / POS) con driver di cassa pluggabile per registratori telematici (RT) e simulatore virtuale, scarico automatico giacenze FEFO per lotti bio, registrazione contabile a Partita Doppia dei corrispettivi e interfaccia Quasar touch-friendly con layout scontrino termico.

**Architecture:** Modelli relazionali `PosStation`, `PosSale`, `PosSaleItem`. Servizio `PosDriverService` con pattern pluggabile (Simulator, Epson ePOS XML, Custom TCP, ESC/POS). Scarico FEFO integrato sui prodotti deperibili. Chiusura corrispettivi automatica in `JournalEntry` (Dare Cassa/POS, Avere Merci e IVA). Interfaccia Quasar `BancoM.vue` con tastierino contanti, calcolo resto e anteprima scontrino termico 80mm.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, Alembic, PostgreSQL 15, Vue 3, Quasar 2.16, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-vendita-al-banco-pos-driver-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Architettura Modulare:** Aggiungere `"pos"` a `AVAILABLE_MODULES` in `backend/app.py`.
- **Scarico FEFO:** Per i prodotti con `in_scadenza == True`, la quantità venduta deve essere prioritariamente scaricata dal lotto bio più prossimo alla scadenza e il codice lotto deve essere salvato nella riga scontrino.
- **Quadratura Contabile:** La scrittura corrispettivi in Partita Doppia deve soddisfare rigorosamente `abs(totale_dare - totale_avere) <= 0.001`.
- **Driver di Default:** Il driver di default della stazione di cassa deve essere `'simulator'`, garantendo funzionamento completo e autonomo in ambienti di sviluppo, test e CI senza hardware RT collegato.

## Review Focus

1. **Persistenza e Relazioni POS:** Creazione tabelle `pos_station`, `pos_sale`, `pos_sale_item` con collegamenti a `product`, `journal_entry` e `partner`.
2. **Numerazione Sequenziale Scontrini:** Formato annuale progressivo `SC-YYYY-XXXX`.
3. **Calcolo Resto e Pagamento:** Rifiuto vendita con HTTP 400 se `importo_pagato < totale_lordo` in modalità contanti.
4. **Scrittura Corrispettivi Partita Doppia:** Generazione della riga di prima nota con quadratura centesimale Dare/Avere.
5. **Output del Driver Simulatore:** Generazione del testo scontrino termico ASCII contenente intestazione, articoli, lotti bio, totale e matricola RT.

---

### Task 1: Modelli Relazionali `PosStation`, `PosSale`, `PosSaleItem` e Migrazione Database

**Files:**
- Create: `backend/models/pos_station.py`
- Create: `backend/models/pos_sale.py`
- Create: `backend/models/pos_sale_item.py`
- Modify: `backend/models/__init__.py`
- Create: `tests/backend/test_pos_bancom.py`

**Interfaces:**
- Produces: Modelli `PosStation`, `PosSale`, `PosSaleItem`.

- [ ] **Step 1: Scrivere test per la persistenza dei modelli POS in `tests/backend/test_pos_bancom.py`**
  ```python
  def test_pos_models_persistence(client):
      from models import db, PosStation, PosSale, PosSaleItem, Product
      with client.application.app_context():
          station = PosStation(
              codice="CASSA_01",
              nome="Cassa Banco Principale",
              driver_tipo="simulator",
              matricola_rt="99MEY123456"
          )
          db.session.add(station)
          db.session.commit()

          p = Product(codice="BIO-MELA", nome="Mela Bio", prezzo_unitario=2.50, aliquota_iva=4.0)
          db.session.add(p)
          db.session.commit()

          sale = PosSale(
              pos_station_id=station.id,
              numero_scontrino="SC-2026-0001",
              totale_lordo=5.00,
              totale_imponibile=4.81,
              totale_iva=0.19,
              metodo_pagamento="contanti",
              importo_pagato=10.00,
              importo_resto=5.00
          )
          db.session.add(sale)
          db.session.commit()

          item = PosSaleItem(
              pos_sale_id=sale.id,
              product_id=p.id,
              quantita=2.0,
              prezzo_unitario=2.50,
              aliquota_iva=4.0,
              subtotale=5.00
          )
          db.session.add(item)
          db.session.commit()

          assert sale.id is not None
          assert len(sale.items) == 1
          assert sale.station.codice == "CASSA_01"
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_pos_bancom.py -v`
  - Expected: FAIL (`ImportError: cannot import name 'PosStation' from 'models'`).

- [ ] **Step 3: Creare `backend/models/pos_station.py`, `backend/models/pos_sale.py`, `backend/models/pos_sale_item.py` e aggiornare `backend/models/__init__.py`**
  - Implementare i modelli con relazioni, campi e metodi `to_dict()`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_pos_bancom.py -v`
  - Expected: PASS.

- [ ] **Step 5: Eseguire la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add pos stations and pos sales models" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Tabelle `pos_station`, `pos_sale`, `pos_sale_item` create su PostgreSQL.

---

### Task 2: Servizio Driver di Cassa Pluggabile (`pos_driver_service.py`)

**Files:**
- Create: `backend/services/pos_driver_service.py`
- Modify: `tests/backend/test_pos_bancom.py`

**Interfaces:**
- Produces: `PosDriverService.print_ticket(sale: PosSale, station: PosStation) -> dict`.

- [ ] **Step 1: Scrivere test per il driver di cassa in `tests/backend/test_pos_bancom.py`**
  - `test_pos_driver_simulator_output`: verifica che `PosDriverService.print_ticket` generi ticket ASCII con matricola, articoli, totale, metodo pagamento e resto.

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_pos_bancom.py -k test_pos_driver_simulator_output -v`
  - Expected: FAIL (`ModuleNotFoundError: No module named 'services.pos_driver_service'`).

- [ ] **Step 3: Implementare `backend/services/pos_driver_service.py`**
  - Implementare `PosDriverService` con metodi `print_ticket`, `_execute_simulator`, `_execute_epson_http`, `_execute_custom_tcp`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_pos_bancom.py -k test_pos_driver_simulator_output -v`
  - Expected: PASS.

---

### Task 3: Backend REST APIs Vendita al Banco, Scarico FEFO e Partita Doppia

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_pos_bancom.py`

**Interfaces:**
- Consumes: Header auth, carrello vendita.
- Produces: `GET /api/pos/stations`, `POST /api/pos/stations`, `PUT /api/pos/stations/<id>`, `GET /api/pos/sales`, `POST /api/pos/sales`, `POST /api/pos/sales/<id>/print`.

- [ ] **Step 1: Scrivere test API in `tests/backend/test_pos_bancom.py`**
  - `test_api_create_pos_sale_with_fefo_and_accounting`: registrazione vendita con scarico FEFO lotto bio, verifica scrittura bilanciata in prima nota contabile e ricezione testo scontrino.
  - `test_api_pos_sale_insufficient_payment_rejected`: rifiuto HTTP 400 se importo pagato < totale.

- [ ] **Step 2: Eseguire i test per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_pos_bancom.py -k "test_api_create_pos_sale or test_api_pos_sale_insufficient" -v`
  - Expected: FAIL (404 Not Found).

- [ ] **Step 3: Aggiungere `"pos"` a `AVAILABLE_MODULES` e implementare gli endpoint in `backend/app.py`**
  - Seed automatico stazione `CASSA_01`.
  - Logica creazione scontrino `SC-YYYY-XXXX`, scarico FEFO, scrittura `JournalEntry` e chiamata `PosDriverService`.

- [ ] **Step 4: Eseguire tutti i test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_pos_bancom.py -v`
  - Expected: PASS (100%).

---

### Task 4: Frontend Quasar in `BancoM.vue`, Rotta Router e Sidebar Navigation

**Files:**
- Create: `frontend/src/components/BancoM.vue`
- Modify: `frontend/src/router.js`
- Modify: `frontend/src/App.vue`
- Create: `tests/frontend/BancoM.spec.js`

**Interfaces:**
- Consumes: `/api/pos/stations`, `/api/pos/sales`, `/api/products`.
- Produces: Maschera POS Touch, tastierino resto, visualizzatore scontrino 80mm.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/BancoM.spec.js`**
  - Verifica rendering catalogo prodotti, aggiunta al carrello, calcolo resto con tasti banconote veloci ed emissione scontrino.

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/BancoM.spec.js`
  - Expected: FAIL (`Cannot find module './BancoM.vue'`).

- [ ] **Step 3: Creare `frontend/src/components/BancoM.vue`, registrare la rotta `/bancom` in `router.js` e la voce di menu in `App.vue`**
  - Schermata cassa touch a 2 colonne.
  - Tastierino banconote rapide (€5, €10, €20, €50).
  - Dialog con scontrino termico stilizzato e tasto stampa.
  - Schede storico scontrini e impostazioni cassa RT.

- [ ] **Step 4: Eseguire test frontend (GREEN)**
  - Run: `npm --prefix frontend run test ../tests/frontend/BancoM.spec.js`
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
  - Emissione di uno scontrino via curl con scarico lotto bio, verifica ticket ASCII e registrazione in prima nota.

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
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo vendita al banco bancom pos con driver registratore telematico e scontrini termici"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
