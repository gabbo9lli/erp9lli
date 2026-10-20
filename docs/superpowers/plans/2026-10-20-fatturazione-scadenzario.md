# Fatturazione Attiva e Scadenzario Pagamenti Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare il modulo di Fatturazione Attiva (Differita TD24 da DDT e Immediata TD01), Castelletto IVA automatico e Scadenzario Rate con quadratura al centesimo (`CreaScadenze`) ispirato a Gestionale ReteBio.

**Architecture:** Modelli SQLAlchemy `Invoice`, `InvoiceItem` e `InvoiceInstallment` su PostgreSQL. Procedura di fatturazione differita atomica che consuma DDT confermati e ne aggiorna lo stato a `fatturato`. Calcolo ripartizione IVA e rate scadenzario con saldo automatico della fattura all'incasso dell'ultima rata. Maschera Quasar responsive con elenco fatture, wizard differita e console crediti.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, Alembic, PostgreSQL 15, Vue 3, Quasar 2.16, Vite, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-20-fatturazione-scadenzario-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Quadratura Contabile:** La somma delle rate generate nello scadenzario DEVE corrispondere esattamente al centesimo al `totale_fattura` (`SUM(rate.importo) == invoice.totale_fattura`).

## Review Focus

1. **Transizione di Stato DDT:** Alla creazione della fattura differita, tutti i DDT inclusi devono passare da `confermato` a `fatturato` e non essere più selezionabili in future fatturazioni.
2. **Castelletto IVA Multi-Aliquota:** Il totale IVA e la ripartizione per aliquota (4%, 10%, 22%) devono essere calcolati accuratamente su ciascuna riga merce.
3. **Quadratura Rate su Importi Dispari:** Pagamenti a più rate con importi con decimali periodici (es. 100.05 / 2) devono attribuire il centesimo di scarto sulla prima o ultima rata garantendo pareggio a zero.
4. **Saldo Automatico Fattura:** All'incasso dell'ultima rata aperta, la fattura deve transitare automaticamente a `saldata`.
5. **Reattività Wizard Frontend:** Il wizard di fatturazione differita deve visualizzare solo i DDT non fatturati del cliente selezionato e aggiornare i totali di anteprima.

---

### Task 1: Backend Models `Invoice`, `InvoiceItem`, `InvoiceInstallment` e Migrazione Database

**Files:**
- Modify: `backend/models.py`
- Create: `tests/backend/test_invoices_installments.py`

**Interfaces:**
- Produces: Classi SQLAlchemy `Invoice`, `InvoiceItem`, `InvoiceInstallment` con relazioni su `Partner`, `Product` e `DeliveryNote`.

- [ ] **Step 1: Scrivere test per la persistenza dei modelli in `tests/backend/test_invoices_installments.py`**
  ```python
  def test_invoice_and_installment_models(client):
      from models import db, Partner, Product, Invoice, InvoiceItem, InvoiceInstallment
      from datetime import date
      with client.application.app_context():
          p = Partner(ragione_sociale="Cliente Fattura Test", tipo="cliente")
          prod = Product(codice="ART-TEST", descrizione="Articolo Test", categoria="fresco", prezzo_vendita=10.0)
          db.session.add_all([p, prod])
          db.session.commit()

          inv = Invoice(
              numero=1,
              anno=2026,
              numero_completo="FT-2026-0001",
              tipo_documento="TD24",
              data_documento=date.today(),
              cliente_id=p.id,
              totale_imponibile=100.0,
              totale_imposta=4.0,
              totale_fattura=104.0,
              stato="emessa"
          )
          db.session.add(inv)
          db.session.commit()

          item = InvoiceItem(
              invoice_id=inv.id,
              product_id=prod.id,
              descrizione=prod.descrizione,
              colli=1,
              quantita=10.0,
              prezzo_unitario=10.0,
              imponibile_riga=100.0,
              aliquota_iva=4
          )
          inst = InvoiceInstallment(
              invoice_id=inv.id,
              numero_rata=1,
              totale_rate=1,
              data_scadenza=date.today(),
              importo=104.0,
              stato="aperta"
          )
          db.session.add_all([item, inst])
          db.session.commit()

          assert inv.id is not None
          assert len(inv.items) == 1
          assert len(inv.installments) == 1
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_invoices_installments.py -v`
  - Expected: FAIL (`ImportError: cannot import name 'Invoice' from 'models'`).

- [ ] **Step 3: Implementare i modelli in `backend/models.py`**
  - Definire `Invoice` con campi: `numero`, `anno`, `numero_completo`, `tipo_documento`, `data_documento`, `cliente_id`, `condizioni_pagamento`, `esigibilita_iva`, `totale_imponibile`, `totale_imposta`, `totale_fattura`, `castelletto_iva`, `stato`, `note`, `to_dict()`.
  - Definire `InvoiceItem` con campi: `invoice_id`, `delivery_note_id`, `product_id`, `descrizione`, `unita_misura`, `colli`, `quantita`, `prezzo_unitario`, `aliquota_iva`, `imponibile_riga`, `lotto`, `data_scadenza`, `to_dict()`.
  - Definire `InvoiceInstallment` con campi: `invoice_id`, `numero_rata`, `totale_rate`, `data_scadenza`, `importo`, `stato`, `data_incasso`, `to_dict()`.

- [ ] **Step 4: Eseguire i test dei modelli (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_invoices_installments.py -v`
  - Expected: PASS.

- [ ] **Step 5: Applicare la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add invoice and installment models" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Nuove tabelle create con successo su PostgreSQL.

---

### Task 2: Backend REST APIs (Fatturazione Differita da DDT, IVA e Scadenzario)

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_invoices_installments.py`

**Interfaces:**
- Consumes: Header di identità, `ddt_ids` confermati, condizioni di pagamento.
- Produces: Endpoint `/api/delivery-notes/unbilled`, `/api/invoices/from-ddt`, `/api/invoices`, `/api/installments`, `/api/installments/<id>/pay`.

- [ ] **Step 1: Scrivere test API in `tests/backend/test_invoices_installments.py`**
  - `test_unbilled_delivery_notes`: verifica che appaiano solo DDT confermati e non fatturati.
  - `test_invoice_differita_from_ddt`: genera fattura TD24, clona righe, calcola castelletto IVA, genera rate e imposta stato DDT a `fatturato`.
  - `test_installments_quadratura_odd_amount`: verifica che rate per `30/60gg fm` con importo 100.05 sommino esattamente a 100.05.
  - `test_pay_installment_and_auto_close_invoice`: registrazione incasso e saldo della fattura.

- [ ] **Step 2: Eseguire test API per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_invoices_installments.py -v`
  - Expected: FAIL (404 / endpoints not found).

- [ ] **Step 3: Implementare gli endpoint e la logica di calcolo in `backend/app.py`**
  - Funzione `calculate_installments(totale, data_doc, condizioni)`: calcola scadenze a fine mese e arrotonda con quadratura sul centesimo.
  - Endpoint `GET /api/delivery-notes/unbilled`.
  - Endpoint `POST /api/invoices/from-ddt`: conversione DDT -> fattura, castelletto IVA, rate, update DDT.
  - Endpoint `GET /api/invoices` e `GET /api/invoices/<int:iid>`.
  - Endpoint `POST /api/invoices` (fattura immediata).
  - Endpoint `GET /api/installments` e `POST /api/installments/<int:inst_id>/pay`.

- [ ] **Step 4: Eseguire la suite di test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/ -v`
  - Expected: 100% test superati.

---

### Task 3: Frontend Views (`Invoices.vue`) e Routing

**Files:**
- Create: `frontend/src/components/Invoices.vue`
- Modify: `frontend/src/router.js`
- Modify: `frontend/src/App.vue`
- Create: `tests/frontend/Invoices.spec.js`

**Interfaces:**
- Consumes: `/api/invoices`, `/api/delivery-notes/unbilled`, `/api/installments`.
- Produces: Maschera Quasar con elenco fatture, wizard differita da DDT e gestione incasso rate.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/Invoices.spec.js`**
  - Verifica rendering tabella fatture, totali e presenza pulsante fatturazione differita.

- [ ] **Step 2: Eseguire test frontend per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/Invoices.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Creare `frontend/src/components/Invoices.vue`**
  - Tabella `<q-table>` Quasar con elenco fatture: Numero, Data, Cliente, Tipo, Imponibile, IVA, Totale, Stato.
  - Sezione / Tab Scadenzario con lista rate e pulsante rapido "Incassa".
  - Wizard modale per fatturazione differita:
    - Selettore Cliente.
    - Tabella DDT non fatturati con checkbox di selezione.
    - Anteprima totali e piano rate.
    - Pulsante "Emetti Fattura Differita".

- [ ] **Step 4: Aggiornare `frontend/src/router.js` e `frontend/src/App.vue`**
  - Aggiungere rotta protetta `/invoices`.
  - Aggiungere il link "Fatture" nella navbar di `App.vue`.

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
  - Fatturare via curl il DDT live `DDT-2026-0001` verificando creazione di `FT-2026-0001` e passaggio del DDT a `fatturato`.

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
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo fatturazione attiva e scadenzario con quadratura rate"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
