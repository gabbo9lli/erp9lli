# Modulo Interscambio Pallet e Buoni Pallet (Legge 182/2025) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare il modulo `pallets` per l'Interscambio Pallet conforme alla Legge 182/2025: tipologie pallet (`PalletType`), emissione Buoni Pallet come titolo di credito (`PalletReceipt`, `PalletReceiptItem` con numerazione `BP-YYYY-XXXX`), partitario Dare/Avere (Spediti vs Resi) e fatturazione automatica per mancata restituzione in regime di Reverse Charge.

**Architecture:** Modelli relazionali in `backend/models/`. Calcolo progressivo saldi per soggetto e formato bancale. Endpoint REST per emissione buoni, registrazione resi a compensazione, consultazione partitario ed emissione fattura di risarcimento ex art. 74 c. 7/8 DPR 633/72. Console Quasar `Pallets.vue` a 3 schede con alert termini di legge e disaccoppiamento `ENABLED_MODULES` (`pallets`).

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, Alembic, PostgreSQL 15, Vue 3, Quasar 2.16, Vite, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-20-interscambio-pallet-legge-182-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Numerazione Buono Pallet:** Generazione progressivo univoco annuale nel formato `BP-YYYY-XXXX` (es. `BP-2026-0001`).
- **Scadenza Restituzione di Legge:** Impostazione automatica della data limite di restituzione a 60 giorni dalla data di emissione (`data_emissione + timedelta(days=60)`).
- **Reverse Charge su Fatturazione Mancata Resa:** La fattura automatica per mancata restituzione deve essere emessa con imponibile pari a `pezzi * valore_risarcimento`, aliquota IVA 0% e causale fiscale che cita l'Art. 74 c. 7/8 DPR 633/72 e L. 182/2025.

## Review Focus

1. **Numerazione Sequenziale Buono Pallet:** Incremento progressivo annuale `BP-2026-0001`, `BP-2026-0002`...
2. **Calcolo Saldo Buono e Chiusura a 'Saldato':** Quando la quantità restituita compensa interamente la quantità consegnata (`saldo_netto == 0`), il buono transita automaticamente a `'saldato'`.
3. **Calcolo Partitario Globale per Soggetto:** Il partitario deve sommare tutti i pallet consegnati e sottrarre tutti i resi per cliente o vettore, esponendo il saldo debitorio netto.
4. **Fatturazione Automatica Reverse Charge:** Verifica che la fattura generata abbia causale corretta e chiuda il buono a `'fatturato'`.
5. **Reattività Sidebar Quasar:** La voce *Interscambio Pallet (L.182)* deve essere condizionata da `activeModules.pallets`.

---

### Task 1: Modelli `PalletType`, `PalletReceipt` & `PalletReceiptItem`, Seed e Migrazione Database

**Files:**
- Create: `backend/models/pallet_type.py`
- Create: `backend/models/pallet_receipt.py`
- Create: `backend/models/pallet_receipt_item.py`
- Modify: `backend/models/__init__.py`
- Create: `tests/backend/test_pallets_interchange.py`

**Interfaces:**
- Produces: Classi SQLAlchemy `PalletType`, `PalletReceipt`, `PalletReceiptItem`.

- [ ] **Step 1: Scrivere test per la persistenza dei modelli pallet in `tests/backend/test_pallets_interchange.py`**
  ```python
  def test_pallet_models_persistence(client):
      from models import db, Partner, PalletType, PalletReceipt, PalletReceiptItem
      from datetime import date, timedelta
      with client.application.app_context():
          partner = Partner(ragione_sociale="Cliente Pallet Test", tipo="cliente")
          ptype = PalletType(codice="EPAL", descrizione="Pallet EUR/EPAL Legno Standard", valore_risarcimento=18.0)
          db.session.add_all([partner, ptype])
          db.session.commit()

          receipt = PalletReceipt(
              numero=1,
              anno=2026,
              numero_completo="BP-2026-0001",
              data_emissione=date.today(),
              data_limite_restituzione=date.today() + timedelta(days=60),
              partner_id=partner.id,
              tipo="uscita",
              totale_consegnati=15,
              totale_restituiti=0,
              saldo_netto=15,
              stato="aperto"
          )
          db.session.add(receipt)
          db.session.commit()

          item = PalletReceiptItem(
              pallet_receipt_id=receipt.id,
              pallet_type_id=ptype.id,
              quantita_consegnata=15,
              quantita_restituita=0,
              saldo_riga=15
          )
          db.session.add(item)
          db.session.commit()

          assert receipt.id is not None
          assert len(receipt.items) == 1
          assert receipt.saldo_netto == 15
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_pallets_interchange.py -v`
  - Expected: FAIL (`ImportError: cannot import name 'PalletType' from 'models'`).

- [ ] **Step 3: Creare `backend/models/pallet_type.py`, `backend/models/pallet_receipt.py`, `backend/models/pallet_receipt_item.py` e aggiornare `backend/models/__init__.py`**
  - Implementare modelli con metodi `to_dict()`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_pallets_interchange.py -v`
  - Expected: PASS.

- [ ] **Step 5: Eseguire la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add pallet interchange models" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Tabelle create con successo su PostgreSQL.

---

### Task 2: Backend REST APIs Buoni Pallet, Partitario Dare/Avere e Fatturazione Reverse Charge

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_pallets_interchange.py`

**Interfaces:**
- Consumes: Header auth, dati buono pallet, richieste di reso e fatturazione mancata resa.
- Produces: Endpoint `/api/pallets/types`, `/api/pallets/receipts`, `/api/pallets/receipts/<id>/return`, `/api/pallets/ledger`, `/api/pallets/receipts/<id>/invoice-unreturned`.

- [ ] **Step 1: Scrivere test API in `tests/backend/test_pallets_interchange.py`**
  - `test_create_pallet_receipt_sequential_and_term`: emissione `BP-YYYY-XXXX`, calcolo scadenza a +60gg.
  - `test_pallet_receipt_return_and_settlement`: restituzione pallet vuoti e passaggio automatico a `'saldato'`.
  - `test_pallet_ledger_balances`: partitario globale saldi debitori per cliente/vettore.
  - `test_invoice_unreturned_pallets_reverse_charge`: fatturazione per mancata resa con Reverse Charge (art. 74 c. 7/8 DPR 633/72) e passaggio del buono a `'fatturato'`.

- [ ] **Step 2: Eseguire test API per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_pallets_interchange.py -v`
  - Expected: FAIL (404 / endpoints not found).

- [ ] **Step 3: Implementare gli endpoint pallet in `backend/app.py`**
  - Includere `"pallets"` in `AVAILABLE_MODULES`.
  - Helper `get_next_pallet_receipt_number(anno)`.
  - Endpoint `GET /api/pallets/types` e `POST /api/pallets/types`.
  - Endpoint `GET /api/pallets/receipts` e `GET /api/pallets/receipts/<int:pid>`.
  - Endpoint `POST /api/pallets/receipts` (emissione buono).
  - Endpoint `POST /api/pallets/receipts/<int:pid>/return` (restituzione e saldo).
  - Endpoint `GET /api/pallets/ledger` (partitario dare/avere).
  - Endpoint `POST /api/pallets/receipts/<int:pid>/invoice-unreturned` (generazione fattura Reverse Charge).

- [ ] **Step 4: Eseguire tutti i test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/ -v`
  - Expected: 100% test superati.

---

### Task 3: Frontend Component `Pallets.vue` e Routing

**Files:**
- Create: `frontend/src/components/Pallets.vue`
- Modify: `frontend/src/router.js`
- Modify: `frontend/src/App.vue`
- Create: `tests/frontend/Pallets.spec.js`

**Interfaces:**
- Consumes: `/api/pallets/receipts`, `/api/pallets/ledger`, `/api/pallets/types`.
- Produces: Maschera Quasar a 3 schede (Buoni Pallet, Partitario Saldi, Tipologie) con alert termini di legge e dialog reso/fatturazione.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/Pallets.spec.js`**
  - Verifica caricamento schede, elenco buoni pallet `BP-2026-xxxx` e partitario saldi.

- [ ] **Step 2: Eseguire test per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/Pallets.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Creare `frontend/src/components/Pallets.vue`**
  - Tab 1: Buoni Pallet (`BP-2026-xxxx`) con filtri, badge scadenza e pulsante "Nuovo Buono Pallet" e "Registra Reso".
  - Tab 2: Partitario Saldi per Cliente/Vettore con pulsante rapido "Fattura Mancata Resa".
  - Tab 3: Tipologie Pallet (anagrafica formati e valori risarcimento).

- [ ] **Step 4: Aggiornare `frontend/src/router.js` e `frontend/src/App.vue`**
  - Aggiungere rotta protetta `/pallets`.
  - Aggiungere voce *"Interscambio Pallet (L.182)"* nella sidebar di `App.vue` sotto Logistica & Magazzino (`v-if="activeModules.pallets"`).

- [ ] **Step 5: Eseguire tutti i test frontend (GREEN)**
  - Run: `npm --prefix frontend run test`
  - Expected: 100% test superati.

---

### Task 4: Verifica Completa ed Esecuzione Test Suite

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
  - Emettere Buono Pallet live via curl, registrare un reso parziale e verificare partitario saldi.

---

### Task 5: Commit Git Firmato GPG

**Files:**
- Repository Git

- [ ] **Step 1: Staging chirurgico dei file modificati**
  ```bash
  git add backend/ frontend/ tests/ docs/superpowers/plans/
  ```

- [ ] **Step 2: Commit firmato GPG**
  ```bash
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo interscambio pallet e buoni pallet legge 182/2025"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
