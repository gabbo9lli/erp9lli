# Modulo Note di Credito (TD04) & Gestione Resi Merci Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare l'emissione e la gestione delle Note di Credito (tipo documento SDI `TD04`) con numerazione dedicata `NC-YYYY-XXXX`, collegamento alla fattura d'origine (`<DatiFattureCollegate>` in XML SDI), compensazione automatica dello scadenzario rate, opzione di reintegro magazzino per resi merci e wizard Quasar in `Invoices.vue`.

**Architecture:** Estensione del modello `Invoice` con campi di tracciamento storno. Endpoint backend per generazione assistita della nota di credito con decurtazione rate aperte. Aggiornamento del builder XML `sdi_service.py` per tracciato `TD04` conforme SDI. Interfaccia Quasar per emissione rapida e visualizzazione badge distintivo.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, Alembic, PostgreSQL 15, Vue 3, Quasar 2.16, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-note-credito-resi-merci-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Numerazione Serie Note di Credito:** Generazione progressivo univoco annuale nel formato `NC-YYYY-XXXX` (es. `NC-2026-0001`).
- **Tracciato XML SDI TD04:** Presenza obbligatoria del blocco `<DatiFattureCollegate>` contenente `<IdDocumento>` e `<Data>` della fattura stornata.
- **Compensazione Scadenzario:** La nota di credito deve poter decurtare automaticamente le rate aperte della fattura d'origine, chiudendole se azzerate.

## Review Focus

1. **Numerazione Indipendente NC:** Verifica che le note di credito utilizzino il prefisso `NC-YYYY-XXXX` senza interferire con la numerazione `FT-YYYY-XXXX`.
2. **Collegamento Fattura d'Origine:** Verifica persistenza dei campi `invoice_origine_id` e `invoice_origine_numero`.
3. **Compensazione Rate dello Scadenzario:** Decurtazione progressiva dell'importo a storno dalle rate aperte fino all'eventuale saldo completo.
4. **Tracciato XML SDI:** Verifica generazione del nodo `<DatiFattureCollegate>` nell'XML esportato.
5. **Reintegro Magazzino Lotti Bio:** Se `reintegro_magazzino = True`, ripristino delle quantità a magazzino per il lotto stornato.

---

### Task 1: Estensione Modello `Invoice` per Note di Credito e Migrazione Database

**Files:**
- Modify: `backend/models/invoice.py`
- Create: `tests/backend/test_credit_notes.py`

**Interfaces:**
- Produces: Campi `invoice_origine_id`, `invoice_origine_numero`, `causale_storno`, `reintegro_magazzino` su `Invoice`.

- [ ] **Step 1: Scrivere test per la persistenza della Nota di Credito in `tests/backend/test_credit_notes.py`**
  ```python
  def test_credit_note_model_persistence(client):
      from models import db, Partner, Invoice
      from datetime import date
      with client.application.app_context():
          customer = Partner(ragione_sociale="Cliente NC Test", tipo="cliente")
          db.session.add(customer)
          db.session.commit()

          inv = Invoice(
              numero=1, anno=2026, numero_completo="FT-2026-0001",
              tipo_documento="TD24", data_documento=date.today(),
              cliente_id=customer.id, totale_imponibile=100.0,
              totale_imposta=4.0, totale_fattura=104.0
          )
          db.session.add(inv)
          db.session.commit()

          nc = Invoice(
              numero=1, anno=2026, numero_completo="NC-2026-0001",
              tipo_documento="TD04", data_documento=date.today(),
              cliente_id=customer.id, totale_imponibile=50.0,
              totale_imposta=2.0, totale_fattura=52.0,
              invoice_origine_id=inv.id, invoice_origine_numero=inv.numero_completo,
              causale_storno="Reso parziale merce avariata",
              reintegro_magazzino=False
          )
          db.session.add(nc)
          db.session.commit()

          assert nc.id is not None
          assert nc.invoice_origine_id == inv.id
          assert nc.tipo_documento == "TD04"
          assert nc.numero_completo == "NC-2026-0001"
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_credit_notes.py -v`
  - Expected: FAIL (`TypeError: 'invoice_origine_id' is an invalid keyword argument for Invoice`).

- [ ] **Step 3: Aggiungere i campi e la relazione in `backend/models/invoice.py`**
  - Implementare campi e aggiornare `to_dict()`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_credit_notes.py -v`
  - Expected: PASS.

- [ ] **Step 5: Eseguire la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add credit note fields to invoice" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Colonne aggiunte con successo alla tabella `invoice` su PostgreSQL.

---

### Task 2: Backend REST Endpoint `/api/invoices/<id>/credit-note` con Compensazione Rate e Reintegro Magazzino

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_credit_notes.py`

**Interfaces:**
- Consumes: ID fattura d'origine, righe da stornare, causale, flag compensazione e reintegro.
- Produces: `POST /api/invoices/<int:iid>/credit-note`.

- [ ] **Step 1: Scrivere test per la generazione della Nota di Credito e compensazione rate in `tests/backend/test_credit_notes.py`**
  - `test_create_credit_note_partial_reversal`: storno parziale di 1 riga con emissione `NC-YYYY-XXXX`.
  - `test_credit_note_installments_compensation`: verifica decurtazione o chiusura della rata aperta nello scadenzario.
  - `test_credit_note_stock_reintegration`: verifica reintegro delle giacenze se `reintegro_magazzino = True`.

- [ ] **Step 2: Eseguire test per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_credit_notes.py -v`
  - Expected: FAIL (404 Not Found).

- [ ] **Step 3: Implementare `get_next_credit_note_number(anno)` e `POST /api/invoices/<int:iid>/credit-note` in `backend/app.py`**
  - Creazione documento `TD04` con progressivo `NC-YYYY-XXXX`.
  - Storno righe merci e calcolo castelletto IVA.
  - Compensazione progressiva sulle rate dello scadenzario della fattura d'origine.
  - Reintegro giacenze magazzino se richiesto.

- [ ] **Step 4: Eseguire tutti i test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_credit_notes.py -v`
  - Expected: PASS (100%).

---

### Task 3: Aggiornamento Tracciato XML SDI per `TD04` (`<DatiFattureCollegate>`)

**Files:**
- Modify: `backend/services/sdi_service.py`
- Modify: `tests/backend/test_credit_notes.py`

**Interfaces:**
- Consumes: Documento `Invoice` con `tipo_documento='TD04'`.
- Produces: XML con nodo `<DatiFattureCollegate>` contenente `<IdDocumento>` e `<Data>`.

- [ ] **Step 1: Scrivere test XML SDI per Nota di Credito in `tests/backend/test_credit_notes.py`**
  - Verifica presenza di `<TipoDocumento>TD04</TipoDocumento>` e blocco `<DatiFattureCollegate>` con gli estremi della fattura d'origine.

- [ ] **Step 2: Eseguire test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_credit_notes.py -v`
  - Expected: FAIL (nodo `<DatiFattureCollegate>` non trovato).

- [ ] **Step 3: Aggiornare `backend/services/sdi_service.py`**
  - Aggiungere il blocco `<DatiFattureCollegate>` in `<DatiGenerali>` se `invoice.tipo_documento == 'TD04'`.

- [ ] **Step 4: Eseguire test (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_credit_notes.py -v`
  - Expected: PASS.

---

### Task 4: Integrazione Frontend in `Invoices.vue`

**Files:**
- Modify: `frontend/src/components/Invoices.vue`
- Modify: `tests/frontend/Invoices.spec.js`

**Interfaces:**
- Consumes: `/api/invoices/<id>/credit-note`.
- Produces: Dialog emissione nota di credito e badge `TD04` nella tabella.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/Invoices.spec.js`**
  - Verifica comparsa pulsante "Emetti Nota di Credito" e visualizzazione badge `TD04`.

- [ ] **Step 2: Eseguire test per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/Invoices.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Aggiornare `frontend/src/components/Invoices.vue`**
  - Aggiungere pulsante *"Nota di Credito"* (`icon="assignment_return"`) nella tabella.
  - Dialog con selezione righe fattura da stornare, motivazione e toggle reintegro/compensazione.
  - Visualizzazione chip distintivo `TD04` e riferimento alla fattura d'origine.

- [ ] **Step 4: Eseguire test frontend (GREEN)**
  - Run: `npm --prefix frontend run test ../tests/frontend/Invoices.spec.js`
  - Expected: PASS.

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
  - Emettere live la nota di credito `NC-2026-0001` a storno di `FT-2026-0001`, verificare compensazione rate e download XML SDI con `<DatiFattureCollegate>`.

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
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo note di credito td04 e gestione resi merci"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
