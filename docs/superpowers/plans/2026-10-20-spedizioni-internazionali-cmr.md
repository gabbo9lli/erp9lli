# Modulo Spedizioni Internazionali e Lettere di Vettura CMR (Export) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare il modulo `cmr` per le Spedizioni Internazionali ed Export conforme alla Convenzione di Ginevra del 1956: modelli `CmrDocument` e `CmrItem` con numerazione annuale `CMR-YYYY-XXXX`, generazione automatica da DDT per destinazioni estere (`nazione != 'IT'`), precompilazione del luogo di carico su Alessandria per vettore LD TRASPORTI, regola delle 21 righe e visualizzatore Quasar `CmrManagement.vue` a 24 caselle standard.

**Architecture:** Modelli relazionali in `backend/models/`. Endpoint REST in `backend/app.py` per generazione da DDT esteri, aggregazione pesi e impaginazione caselle CMR. Integrazione con tasto rapido in `DeliveryNotes.vue` per DDT esteri e disaccoppiamento mediante feature flag `cmr` in `AVAILABLE_MODULES`.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, Alembic, PostgreSQL 15, Vue 3, Quasar 2.16, Vite, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-20-spedizioni-internazionali-cmr-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Numerazione Lettera di Vettura CMR:** Generazione progressivo univoco annuale nel formato `CMR-YYYY-XXXX` (es. `CMR-2026-0001`).
- **Precompilazione Alessandria per LD Trasporti:** Se il vettore del DDT è *"LD TRASPORTI"*, il campo `luogo_carico` deve essere precompilato automaticamente su `"ALESSANDRIA (AL)"`.
- **Regola 21 Righe:** Con numero righe $\le 21$, `ha_allegato_righe = False`; con numero righe $> 21$, `ha_allegato_righe = True`.

## Review Focus

1. **Attivazione da DDT Estero:** Generazione automatica consentita per clienti con `nazione != 'IT'` (es. `BE`, `FR`, `DE`).
2. **Precompilazione Hub LD Trasporti:** Luogo di carico automaticamente impostato su `"ALESSANDRIA (AL)"` se vettore è LD Trasporti.
3. **Regola Intelligente delle 21 Righe:** Verifica del flag `ha_allegato_righe` in funzione del numero di righe merci.
4. **Struttura 24 Caselle CMR:** L'endpoint `/api/cmr/<id>/print` deve esporre correttamente le 24 caselle della Convenzione di Ginevra.
5. **Reattività Sidebar Quasar:** La voce *Lettere di Vettura (CMR)* deve comparire solo se `activeModules.cmr` è abilitato.

---

### Task 1: Modelli `CmrDocument` & `CmrItem` e Migrazione Database

**Files:**
- Create: `backend/models/cmr_document.py`
- Create: `backend/models/cmr_item.py`
- Modify: `backend/models/__init__.py`
- Create: `tests/backend/test_cmr_export.py`

**Interfaces:**
- Produces: Classi SQLAlchemy `CmrDocument`, `CmrItem`.

- [ ] **Step 1: Scrivere test per la persistenza dei modelli CMR in `tests/backend/test_cmr_export.py`**
  ```python
  def test_cmr_models_persistence(client):
      from models import db, Partner, CmrDocument, CmrItem
      from datetime import date
      with client.application.app_context():
          dest = Partner(ragione_sociale="Bio c' Bon Bruxelles", nazione="BE", tipo="cliente")
          vett = Partner(ragione_sociale="LD Trasporti Srl", nazione="IT", tipo="vettore")
          db.session.add_all([dest, vett])
          db.session.commit()

          cmr = CmrDocument(
              numero=1,
              anno=2026,
              numero_completo="CMR-2026-0001",
              data_documento=date.today(),
              cliente_id=dest.id,
              vettore_id=vett.id,
              luogo_carico="ALESSANDRIA (AL)",
              luogo_consegna="Rue de la Loi 15, Bruxelles (BE)",
              targa_automezzo="FX982KJ",
              targa_rimorchio="XA112LL",
              totale_colli=50,
              peso_totale_netto=500.0,
              peso_totale_lordo=525.0
          )
          db.session.add(cmr)
          db.session.commit()

          item = CmrItem(
              cmr_document_id=cmr.id,
              riga_numero=1,
              contrassegno_lotto="LOTTO-BIO-2026",
              numero_colli=50,
              modo_imballaggio="Casse su Pallet EPAL",
              natura_merce="Arance Tarocco Biologiche",
              codice_nc="08051020",
              peso_netto_kg=500.0,
              peso_lordo_kg=525.0
          )
          db.session.add(item)
          db.session.commit()

          assert cmr.id is not None
          assert len(cmr.items) == 1
          assert cmr.numero_completo == "CMR-2026-0001"
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_cmr_export.py -v`
  - Expected: FAIL (`ImportError: cannot import name 'CmrDocument' from 'models'`).

- [ ] **Step 3: Creare `backend/models/cmr_document.py`, `backend/models/cmr_item.py` e aggiornare `backend/models/__init__.py`**
  - Implementare modelli con metodi `to_dict()`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_cmr_export.py -v`
  - Expected: PASS.

- [ ] **Step 5: Eseguire la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add cmr international shipping models" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Tabelle create con successo su PostgreSQL.

---

### Task 2: Backend REST APIs CMR, Regola 21 Righe e Precompilazione Hub Alessandria

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_cmr_export.py`

**Interfaces:**
- Consumes: Header auth, dati DDT esteri, richieste di emissione e stampa CMR.
- Produces: Endpoint `/api/cmr`, `/api/cmr/<id>`, `/api/cmr/from-ddt/<ddt_id>`, `/api/cmr/<id>/print`.

- [ ] **Step 1: Scrivere test API in `tests/backend/test_cmr_export.py`**
  - `test_create_cmr_from_ddt_with_alessandria_hub`: verifica generazione automatica da DDT con cliente estero e precompilazione luogo carico *"ALESSANDRIA (AL)"* per vettore *"LD TRASPORTI"*.
  - `test_cmr_21_rows_rule_and_attachment_flag`: verifica che 10 righe abbiano `ha_allegato_righe=False` e 25 righe abbiano `ha_allegato_righe=True`.
  - `test_cmr_print_format_boxes`: verifica presenza delle caselle convenzionali CMR nel payload di stampa.

- [ ] **Step 2: Eseguire test API per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_cmr_export.py -v`
  - Expected: FAIL (404 / endpoints not found).

- [ ] **Step 3: Implementare gli endpoint CMR in `backend/app.py`**
  - Includere `"cmr"` in `AVAILABLE_MODULES`.
  - Helper `get_next_cmr_number(anno)`.
  - Endpoint `GET /api/cmr` e `GET /api/cmr/<int:cid>`.
  - Endpoint `POST /api/cmr/from-ddt/<int:ddt_id>` (generazione automatica da DDT).
  - Endpoint `POST /api/cmr` (manuale) e `PUT /api/cmr/<int:cid>`.
  - Endpoint `GET /api/cmr/<int:cid>/print` (struttura 24 caselle CMR).

- [ ] **Step 4: Eseguire tutti i test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/ -v`
  - Expected: 100% test superati.

---

### Task 3: Integrazione Tasto CMR in `DeliveryNotes.vue`

**Files:**
- Modify: `frontend/src/components/DeliveryNotes.vue`
- Modify: `tests/frontend/DeliveryNotes.spec.js`

**Interfaces:**
- Consumes: `/api/cmr/from-ddt/<id>`.
- Produces: Pulsante di emissione rapida CMR nelle righe DDT di clienti esteri.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/DeliveryNotes.spec.js`**
  - Verifica comparsa pulsante CMR se cliente ha `nazione !== 'IT'`.

- [ ] **Step 2: Eseguire test per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/DeliveryNotes.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Aggiornare `frontend/src/components/DeliveryNotes.vue`**
  - Nella colonna azioni della tabella DDT, se `props.row.cliente?.nazione !== 'IT'`, mostrare pulsante `CMR` (`icon="public"`).
  - Al click, invocare `POST /api/cmr/from-ddt/<id>` con feedback e reindirizzamento opzionale a `/cmr`.

- [ ] **Step 4: Eseguire test frontend (GREEN)**
  - Run: `npm --prefix frontend run test ../tests/frontend/DeliveryNotes.spec.js`
  - Expected: PASS.

---

### Task 4: Frontend Component `CmrManagement.vue` e Routing

**Files:**
- Create: `frontend/src/components/CmrManagement.vue`
- Modify: `frontend/src/router.js`
- Modify: `frontend/src/App.vue`
- Create: `tests/frontend/CmrManagement.spec.js`

**Interfaces:**
- Consumes: `/api/cmr`.
- Produces: Maschera Quasar con elenco lettere di vettura e visualizzatore convenzionale a 24 caselle CMR.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/CmrManagement.spec.js`**
  - Verifica caricamento elenco lettere di vettura e rendering caselle CMR.

- [ ] **Step 2: Eseguire test per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/CmrManagement.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Creare `frontend/src/components/CmrManagement.vue`**
  - Tabella lettere di vettura con codice nazione estera, vettore, targhe, colli, pesi netti/lordi.
  - Dialog / Viewer del modello CMR convenzionale a 24 caselle con visualizzazione dicitura allegato se `ha_allegato_righe == true`.
  - Dialog modifica dati automezzo (targhe, luogo carico, note doganali).

- [ ] **Step 4: Aggiornare `frontend/src/router.js` e `frontend/src/App.vue`**
  - Aggiungere rotta protetta `/cmr`.
  - Aggiungere voce *"Lettere di Vettura (CMR)"* nella sidebar di `App.vue` sotto Logistica & Magazzino (`v-if="activeModules.cmr"`).

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
  - Emettere un DDT per cliente belga (*Bio c' Bon*) con vettore *LD Trasporti*.
  - Invocare la generazione automatica del CMR via curl e verificare precompilazione Alessandria e modello a 24 caselle.

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
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo spedizioni internazionali cmr export con regola 21 righe"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
