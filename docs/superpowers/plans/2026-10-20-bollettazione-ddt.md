# Bollettazione (DDT - Documenti di Trasporto) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare il modulo di Bollettazione (DDT) ispirato a ReteBio con modelli relazionali PostgreSQL, numerazione progressiva annuale automatica, vincoli di tracciabilità biologica (lotti e scadenze), ciclo di vita a stati (Bozza/Confermato) e interfaccia reattiva Quasar.

**Architecture:** Modelli SQLAlchemy `DeliveryNote` (testata) e `DeliveryNoteItem` (righe) con integrità referenziale su `Partner` e `Product`. API REST Flask protette da `@require_auth()` con validazione di filiera bio e aggregazione automatica di colli e pesi. Maschera Quasar responsive con lista e form dinamico righe.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, Alembic, PostgreSQL 15, Vue 3, Quasar 2.16, Vite, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-20-bollettazione-ddt-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Integrità Referenziale:** Il campo `cliente_id` deve puntare a un partner esistente; se un DDT viene eliminato in stato bozza, le relative righe devono essere eliminate a cascata (`ondelete='CASCADE'`).

## Review Focus

1. **Numerazione Progressiva Annuale:** Inserendo più DDT nello stesso anno solare, il progressivo deve incrementarsi senza salti (`DDT-2026-0001`, `DDT-2026-0002`).
2. **Validazione Lotti/Scadenze Bio:** Se una riga merce contiene un prodotto con `in_scadenza == True`, l'assenza di `lotto` o `data_scadenza` deve sollevare errore 400 Bad Request.
3. **Calcolo Totali Colli e Pesi:** Il totale colli, peso netto e totale imponibile della testata devono corrispondere esattamente alla somma delle righe.
4. **Immutabilità DDT Confermato:** Una volta invocato `/api/delivery-notes/<id>/confirm`, qualsiasi tentativo di PUT o DELETE deve essere respinto con errore 400.
5. **Reattività Frontend:** L'editor del DDT deve calcolare i totali in tempo reale e visualizzare gli stati con badge colorati.

---

### Task 1: Backend Models `DeliveryNote` e `DeliveryNoteItem` e Migrazione Database

**Files:**
- Modify: `backend/models.py`
- Create: `tests/backend/test_delivery_notes.py`

**Interfaces:**
- Produces: Classi SQLAlchemy `DeliveryNote` e `DeliveryNoteItem` con relazioni su `Partner` e `Product`.

- [ ] **Step 1: Scrivere test per la persistenza dei modelli in `tests/backend/test_delivery_notes.py`**
  ```python
  def test_delivery_note_model_creation(client):
      from models import db, Partner, Product, DeliveryNote, DeliveryNoteItem
      from datetime import date
      with client.application.app_context():
          client_p = Partner(ragione_sociale="Supermercato Bio", tipo="cliente")
          prod = Product(codice="BIO-PERA", descrizione="Pere Abate Bio", categoria="fresco", prezzo_vendita=3.20)
          db.session.add_all([client_p, prod])
          db.session.commit()

          ddt = DeliveryNote(
              numero=1,
              anno=2026,
              numero_completo="DDT-2026-0001",
              data_documento=date.today(),
              cliente_id=client_p.id,
              causale_trasporto="Vendita"
          )
          db.session.add(ddt)
          db.session.commit()

          item = DeliveryNoteItem(
              delivery_note_id=ddt.id,
              product_id=prod.id,
              descrizione=prod.descrizione,
              colli=10,
              quantita=100.0,
              prezzo_unitario=3.20
          )
          db.session.add(item)
          db.session.commit()

          assert ddt.id is not None
          assert len(ddt.items) == 1
          assert ddt.stato == "bozza"
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_delivery_notes.py -v`
  - Expected: FAIL (`ImportError: cannot import name 'DeliveryNote' from 'models'`).

- [ ] **Step 3: Implementare i modelli in `backend/models.py`**
  - Definire `DeliveryNote` con campi: `numero`, `anno`, `numero_completo`, `data_documento`, `data_trasporto`, `cliente_id`, `vettore_id`, `causale_trasporto`, `porto`, `aspetto_beni`, `colli_totali`, `peso_totale_netto`, `peso_totale_lordo`, `totale_imponibile`, `stato`, `note` e `to_dict()`.
  - Definire `DeliveryNoteItem` con campi: `delivery_note_id`, `product_id`, `descrizione`, `unita_misura`, `colli`, `quantita`, `prezzo_unitario`, `aliquota_iva`, `lotto`, `data_scadenza` e `to_dict()`.

- [ ] **Step 4: Eseguire i test dei modelli (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_delivery_notes.py -v`
  - Expected: PASS.

- [ ] **Step 5: Applicare la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add delivery note models" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Nuove tabelle create con successo su PostgreSQL.

---

### Task 2: Backend REST APIs (`/api/delivery-notes`) con Numerazione Annuale e Validazione Bio

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_delivery_notes.py`

**Interfaces:**
- Consumes: Header di identità `X-Forwarded-*`, payload JSON con testata e righe merci.
- Produces: Endpoint completi `/api/delivery-notes`, `/api/delivery-notes/<id>`, `/api/delivery-notes/<id>/confirm`.

- [ ] **Step 1: Scrivere test API in `tests/backend/test_delivery_notes.py`**
  - `test_create_delivery_note_with_items`: creazione atomica, calcolo progressivo annuale, calcolo totali colli e imponibile.
  - `test_auto_numbering_sequential`: secondo DDT nello stesso anno riceve progressivo `2`.
  - `test_bio_traceability_validation`: articolo con `in_scadenza == True` senza lotto/scadenza respinto con errore 400.
  - `test_confirm_delivery_note`: transizione a `confermato` e blocco modifiche successive (400 su PUT/DELETE).

- [ ] **Step 2: Eseguire test API per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_delivery_notes.py -v`
  - Expected: FAIL (404 / endpoints not found).

- [ ] **Step 3: Implementare gli endpoint in `backend/app.py`**
  - Helper di numerazione: calcolo automatico `MAX(numero) + 1` filtrato per `anno`.
  - Endpoint `GET /api/delivery-notes` e `GET /api/delivery-notes/<int:did>`.
  - Endpoint `POST /api/delivery-notes`: validazione biologica dei lotti e scadenze, calcolo somme e inserimento atomico.
  - Endpoint `PUT /api/delivery-notes/<int:did>` e `DELETE /api/delivery-notes/<int:did>` con verifica `stato == 'bozza'`.
  - Endpoint `POST /api/delivery-notes/<int:did>/confirm` per confermare formalmente il documento.

- [ ] **Step 4: Eseguire la suite di test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/ -v`
  - Expected: 100% test superati.

---

### Task 3: Frontend Views (`DeliveryNotes.vue`) e Routing

**Files:**
- Create: `frontend/src/components/DeliveryNotes.vue`
- Modify: `frontend/src/router.js`
- Modify: `frontend/src/App.vue`
- Create: `tests/frontend/DeliveryNotes.spec.js`

**Interfaces:**
- Consumes: `/api/delivery-notes`, `/api/partners`, `/api/products`.
- Produces: Interfaccia Quasar con elenco documenti, badge di stato, editor modale con griglia articoli, lotti bio e calcolo totali.

- [ ] **Step 1: Scrivere il test frontend in `tests/frontend/DeliveryNotes.spec.js`**
  - Verifica rendering tabella DDT, visualizzazione numero documento, badge di stato e totale colli.

- [ ] **Step 2: Eseguire il test frontend per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/DeliveryNotes.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Creare `frontend/src/components/DeliveryNotes.vue`**
  - Tabella `<q-table>` Quasar con colonne: Numero, Data, Cliente, Vettore, Colli, Quantità, Imponibile, Stato.
  - Dialog modale per nuovo DDT / modifica bozza:
    - Selettore Cliente e Vettore da `/api/partners`.
    - Tabella righe dinamica con selezione articolo da `/api/products`.
    - Campi colli, quantità, prezzo unitario e campi Bio (lotto e scadenza).
    - Box di riepilogo totali in tempo reale (Colli, Quantità, Imponibile).
    - Pulsanti "Salva Bozza" e "Conferma DDT".

- [ ] **Step 4: Aggiornare `frontend/src/router.js` e `frontend/src/App.vue`**
  - Aggiungere rotta protetta `/delivery-notes`.
  - Aggiungere il link "Bolle (DDT)" nella navbar di `App.vue`.

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

- [ ] **Step 4: Test live delle API nel container**
  - Creare un DDT di test tramite curl e verificare calcolo totali e risposta 201.

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
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo bollettazione ddt con tracciabilita lotti bio e stati"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
