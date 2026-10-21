# Modulo Fatturazione Elettronica SDI (Tracciato XML FPR12) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare la generazione e validazione del tracciato XML standard per la Fattura Elettronica SDI (FatturaPA v1.2.2 / FPR12), con gestione differite TD24 (blocchi `<DatiDDT>`), nature IVA per Reverse Charge (`N6.7`) ed export (`N3.2`), rate di pagamento con IBAN e pulsante di download in `Invoices.vue`.

**Architecture:** Modulo di servizio dedicato `backend/services/sdi_service.py` per costruzione XML e validazione formale. Endpoint Flask per streaming del file `.xml` con naming standard `IT<CF>_<Progressivo>.xml`. Pulsante rapido di download e badge di conformità fiscale in `Invoices.vue`.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, xml.etree.ElementTree / minidom, Vue 3, Quasar 2.16, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-fatturazione-elettronica-sdi-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Tracciato XML Ufficiale:** Versione `FPR12` con namespace `xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"`.
- **Naming File SDI:** `IT01234567890_XXXXX.xml` (dove `01234567890` è il codice fiscale del cedente e `XXXXX` un codice univoco a 5 caratteri alfanumerici).
- **Blocchi DatiDDT:** Per le fatture differite `TD24`, ogni riga proveniente da DDT deve generare il nodo `<DatiDDT>` con `<NumeroDDT>` e `<DataDDT>`.

## Review Focus

1. **Intestazione e Dati Trasmissione:** Presenza di `<FormatoTrasmissione>FPR12</FormatoTrasmissione>` e `<CodiceDestinatario>` a 7 caratteri (o `0000000` con `<PECDestinatario>`).
2. **Fatture Differite TD24:** Nodi `<DatiDDT>` generati correttamente per ciascun DDT d'origine.
3. **Mappatura Nature IVA su Aliquota 0%:** Se Reverse Charge per pallet -> `<Natura>N6.7</Natura>`; se cliente UE estero -> `<Natura>N3.2</Natura>`.
4. **Dati Pagamento & Rate:** Nodi `<DatiPagamento>` con `<ModalitaPagamento>MP05</ModalitaPagamento>`, importo, data scadenza e `<IBAN>`.
5. **Validatore Preventivo:** L'endpoint `/api/invoices/<id>/sdi-validate` segnala errori se mancano P.IVA o Codice SDI/PEC.

---

### Task 1: Backend Service `sdi_service.py` per Generazione XML FPR12 e Validazione

**Files:**
- Create: `backend/services/sdi_service.py`
- Create: `tests/backend/test_sdi_export.py`

**Interfaces:**
- Produces: `validate_sdi_invoice(invoice)` e `generate_sdi_xml(invoice, cedente=None) -> tuple[str, str]`.

- [ ] **Step 1: Scrivere test per la generazione del tracciato XML in `tests/backend/test_sdi_export.py`**
  ```python
  def test_generate_sdi_xml_differita_td24(client):
      from services.sdi_service import generate_sdi_xml, validate_sdi_invoice
      # Creazione fattura TD24 con DDT associato e verifica XML
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_sdi_export.py -v`
  - Expected: FAIL (`ModuleNotFoundError: No module named 'services'`).

- [ ] **Step 3: Implementare `backend/services/sdi_service.py`**
  - Costruzione dell'albero XML con `xml.etree.ElementTree`.
  - Mappatura completa di Header, Body, DatiGeneraliDocumento, DatiDDT, DatiBeniServizi, DatiRiepilogo, DatiPagamento.
  - Funzione `validate_sdi_invoice`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_sdi_export.py -v`
  - Expected: PASS.

---

### Task 2: Backend REST Endpoints `/api/invoices/<id>/xml` e `/api/invoices/<id>/sdi-validate`

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_sdi_export.py`

**Interfaces:**
- Consumes: Header auth, ID fattura.
- Produces: `GET /api/invoices/<int:id>/xml` e `GET /api/invoices/<int:id>/sdi-validate`.

- [ ] **Step 1: Scrivere test per gli endpoint REST in `tests/backend/test_sdi_export.py`**
  - Verifica download con `Content-Type: application/xml` e `Content-Disposition`.
  - Verifica validazione SDI via API.

- [ ] **Step 2: Eseguire test API per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_sdi_export.py -v`
  - Expected: FAIL (404 Not Found).

- [ ] **Step 3: Implementare gli endpoint in `backend/app.py`**
  - Integrazione di `generate_sdi_xml` e `validate_sdi_invoice`.

- [ ] **Step 4: Eseguire tutti i test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_sdi_export.py -v`
  - Expected: PASS (100%).

---

### Task 3: Integrazione Frontend in `Invoices.vue`

**Files:**
- Modify: `frontend/src/components/Invoices.vue`
- Modify: `tests/frontend/Invoices.spec.js`

**Interfaces:**
- Consumes: `/api/invoices/<id>/xml` e `/api/invoices/<id>/sdi-validate`.
- Produces: Pulsante di download rapido XML e dialog con stato di conformità SDI.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/Invoices.spec.js`**
  - Verifica rendering pulsante XML e apertura dialog con badge SDI.

- [ ] **Step 2: Eseguire test per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/Invoices.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Aggiornare `frontend/src/components/Invoices.vue`**
  - Aggiungere pulsante `XML` (`icon="code"`) nella tabella.
  - Aggiungere sezione conformità SDI e pulsante *"Scarica XML Fattura Elettronica"* nel dialog di dettaglio.

- [ ] **Step 4: Eseguire test frontend (GREEN)**
  - Run: `npm --prefix frontend run test ../tests/frontend/Invoices.spec.js`
  - Expected: PASS.

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
  - Testare il download XML live della fattura differita `FT-2026-0001` e della fattura pallet `FT-2026-0002` con Reverse Charge.

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
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo fatturazione elettronica sdi con tracciato xml fpr12"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
