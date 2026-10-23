# Stampa Etichette Barcode Termiche (ZPL, Code 128, Formati Bancale e Collo) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare il modulo di generazione e stampa etichette barcode termiche (`BarcodeLabelService`) con codifica Code 128 vettoriale SVG, emissione ZPL per stampanti industriali Zebra, layout termico 100×150 mm (bancale con dati bio) e 50×30 mm (collo), e dialogo Quasar con anteprima e stampa da browser.

**Architecture:** Servizio `BarcodeLabelService` in puro Python (senza dipendenze native pesanti) con encoder Code 128, generatore ZPL a 203 DPI e renderer HTML/CSS `@media print`. Endpoint REST per generazione on-demand e integrazione diretta con righe DDT (`DeliveryNotes.vue`) ed Entrata Merci (`Purchases.vue`). Componente Quasar `BarcodeLabelsDialog.vue` per anteprima interattiva e stampa.

**Tech Stack:** Python 3.11, Flask, ZPL II, SVG vettoriale, Vue 3, Quasar 2.16, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-stampa-etichette-barcode-termiche-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Zero Dipendenze Native Esterne:** La codifica Code 128 deve essere implementata in Python puro per generare stringhe SVG e comandi ZPL validi senza librerie binarie C o wrapper dipendenti dall'host.
- **Tracciabilità Biologica nelle Etichette:** Le etichette di bancale e collo devono riportare obbligatoriamente: Denominazione Articolo, Lotto, Data Scadenza, Origine, Pesi (Netto/Lordo/Tara) ed Ente Certificatore Bio.
- **Tracciamento Event Bus:** Ogni richiesta di generazione etichette deve essere registrata su Event Bus con canale `AUDIT` e categoria `LOGISTICA`.

## Review Focus

1. **Validità Algoritmo Code 128:** Calcolo corretto del checksum modulo 103 e corretta alternanza barre/spazi.
2. **Sintassi ZPL II:** Emissione stringa ZPL valida con delimitatori `^XA` e `^XZ`, e comando barcode `^BC`.
3. **Generazione da DDT Reale:** Endpoint `/api/delivery-notes/<id>/labels` legge correttamente tutte le righe del documento, aggregando colli e pesi.
4. **Resilienza e Fallback:** Gestione valori mancanti o opzionali (es. data scadenza o tara) con placeholder coerenti senza sollevare eccezioni.
5. **Anteprima Quasar:** Visualizzazione corretta del barcode SVG e possibilità di copiare la stringa ZPL negli appunti.

---

### Task 1: Servizio `BarcodeLabelService` (Code 128 SVG Vettoriale e Generatore ZPL Bancale/Collo)

**Files:**
- Create: `backend/services/barcode_label_service.py`
- Create: `tests/backend/test_barcode_labels.py`

**Interfaces:**
- Produces: `BarcodeLabelService.generate_code128_svg`, `generate_pallet_zpl`, `generate_collo_zpl`, `render_pallet_html`, `render_collo_html`.

- [ ] **Step 1: Scrivere test per `BarcodeLabelService` in `tests/backend/test_barcode_labels.py`**
  ```python
  def test_barcode_code128_svg_generation():
      from services.barcode_label_service import BarcodeLabelService
      svg = BarcodeLabelService.generate_code128_svg("BIO-ARAN-2026")
      assert svg.startswith("<svg")
      assert svg.endswith("</svg>")
      assert "<rect" in svg

  def test_pallet_zpl_generation():
      from services.barcode_label_service import BarcodeLabelService
      data = {
          "descrizione": "Arance Tarocco Bio Sicilia",
          "codice_articolo": "BIO-ARAN-TRC",
          "lotto": "LOTTO-TRC-01",
          "data_scadenza": "2026-11-30",
          "colli": 48,
          "peso_netto": 480.0,
          "peso_lordo": 505.0,
          "tara": 25.0,
          "origine": "Italia - Sicilia",
          "ente_certificatore": "IT-BIO-009 CCPB"
      }
      zpl = BarcodeLabelService.generate_pallet_zpl(data)
      assert zpl.startswith("^XA")
      assert zpl.endswith("^XZ")
      assert "^BC" in zpl
      assert "Arance Tarocco Bio Sicilia" in zpl
      assert "LOTTO-TRC-01" in zpl
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_barcode_labels.py -v`
  - Expected: FAIL (`ModuleNotFoundError: No module named 'services.barcode_label_service'`).

- [ ] **Step 3: Implementare `backend/services/barcode_label_service.py`**
  - Implementare tabella codici Code 128 Subset B, calcolo checksum modulo 103, generatore SVG vettoriale, generatori ZPL bancale/collo e renderer HTML.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_barcode_labels.py -v`
  - Expected: PASS.

---

### Task 2: Backend REST APIs Generazione Etichette e Integrazione DDT / Entrate Merci

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_barcode_labels.py`

**Interfaces:**
- Produces: `POST /api/labels/generate`, `GET /api/delivery-notes/<int:id>/labels`, `GET /api/purchases/<int:id>/labels`.

- [ ] **Step 1: Scrivere test API in `tests/backend/test_barcode_labels.py`**
  - `test_api_labels_generate_endpoint`: verifica endpoint on-demand con risposta ZPL, SVG e HTML.
  - `test_api_delivery_note_labels_generation`: verifica generazione etichette bancale per tutte le righe di un DDT reale.

- [ ] **Step 2: Eseguire i test per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_barcode_labels.py -k "test_api" -v`
  - Expected: FAIL (404 Not Found).

- [ ] **Step 3: Implementare gli endpoint in `backend/app.py`**
  - Esporre le route `/api/labels/generate`, `/api/delivery-notes/<id>/labels`, `/api/purchases/<id>/labels` e integrazione con `dispatch_event`.

- [ ] **Step 4: Eseguire tutti i test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_barcode_labels.py -v`
  - Expected: PASS (100%).

---

### Task 3: Frontend Quasar `BarcodeLabelsDialog.vue` e Integrazione in DDT e Catalogo

**Files:**
- Create: `frontend/src/components/BarcodeLabelsDialog.vue`
- Modify: `frontend/src/components/DeliveryNotes.vue`
- Modify: `frontend/src/components/ProductCatalog.vue`
- Create: `tests/frontend/BarcodeLabels.spec.js`

**Interfaces:**
- Consumes: `/api/labels/generate`, `/api/delivery-notes/<id>/labels`.
- Produces: Dialog interattivo anteprima etichetta termica 100x150 mm con barcode SVG, pulsanti stampa browser e ZPL.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/BarcodeLabels.spec.js`**
  - Verifica rendering anteprima etichetta bancale, barcode SVG e pulsanti azione.

- [ ] **Step 2: Eseguire test per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/BarcodeLabels.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Implementare `BarcodeLabelsDialog.vue` e integrare i pulsanti in `DeliveryNotes.vue` e `ProductCatalog.vue`**
  - Layout realistico termico 100×150 mm e 50×30 mm con diciture bio.
  - Pulsanti Stampa Browser (`window.print()`), Copia ZPL e Download ZPL.
  - Tasto *"Etichette Bancale"* in `DeliveryNotes.vue` e *"Stampa Etichetta"* in `ProductCatalog.vue`.

- [ ] **Step 4: Eseguire test frontend (GREEN)**
  - Run: `npm --prefix frontend run test ../tests/frontend/BarcodeLabels.spec.js`
  - Expected: PASS (100%).

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

- [ ] **Step 4: Test live E2E nel container Docker**
  - Chiamata curl su `/api/labels/generate`, verifica stringa ZPL valida e SVG generato.

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
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo stampa etichette barcode termiche zpl code128 bancale e collo con dati biologici"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
