# Domain Services (Clean Architecture) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disaccoppiare interamente le regole aziendali dai router HTTP creando i Domain Services (`OrderService`, `DeliveryNoteService`, `InvoiceService`, `AccountingService`, `PalletService`, `CmrService`, `PosSaleService`).

**Architecture:** Adozione della Clean Architecture / Domain-Driven Design (DDD). I router (livello HTTP) si limiteranno a estrarre i payload Pydantic e delegare ai Domain Services (livello di Dominio) la logica di calcolo, validazione transazionale e interazione con SQLAlchemy. 

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2.

**Spec:** Refactoring "Opzione C" - Disaccoppiamento della Business Logic.

## Global Constraints
- **TDD:** Non è permesso scrivere codice di business senza aver prima eseguito i test del rispettivo dominio. Fortunatamente, i test di integrazione in `tests/backend/` fungeranno da test di regressione (refactoring Red-Green-Refactor su scala macro).
- **Git & GPG:** L'agente DEVE firmare tutti i commit (`git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."`).
- **Nessuna regressione logica:** I flussi applicativi (castelletto IVA, rate, evasione FEFO, pareggio P.D.) restano identici.

## Review Focus
1. **Transaction Leak:** Assicurarsi che i Domain Services accettino `db: Session` ma **non facciano `db.commit()` se devono essere orchestrati** da altri servizi. Il commit può avvenire nel servizio o nel router in base al pattern scelto (opteremo per commit nel router o nel Service a grana grossa).
2. **Missing Imports:** Il refactoring sposterà porzioni enormi di codice. Fare attenzione agli import di EventDispatcher, Service e Model incrociati (Circular Imports).
3. **Event Dispatching:** `dispatch_event` deve continuare a funzionare e ricevere la sessione `db` corretta.

---

### Task 1: `OrderService` e `DeliveryNoteService` (Logistica e Ordini)

**Files:**
- Create: `backend/services/order_service.py`
- Create: `backend/services/delivery_note_service.py`
- Modify: `backend/api/routers/orders.py`
- Modify: `backend/api/routers/delivery_notes.py`
- Test: `tests/backend/test_orders_and_modules.py`, `tests/backend/test_delivery_notes.py`

**Interfaces:**
- Produces: `OrderService.create_order`, `OrderService.fulfill_to_ddt`, `DeliveryNoteService.create_delivery_note`, `DeliveryNoteService.confirm_delivery_note`.

- [ ] **Step 1: Creare `backend/services/order_service.py` e `backend/services/delivery_note_service.py`**
  - Spostare la logica di `create_order`, `update_order`, `fulfill_order_to_ddt` in `OrderService` come `@staticmethod` / `classmethod`.
  - Spostare `create_delivery_note`, `confirm_delivery_note` in `DeliveryNoteService`.

- [ ] **Step 2: Aggiornare `orders.py` e `delivery_notes.py`**
  - I router chiameranno `return OrderService.create_order(db, payload)`.

- [ ] **Step 3: Verificare che i test continuino a passare**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_orders_and_modules.py tests/backend/test_delivery_notes.py -v`
  - Expected: PASS.

- [ ] **Step 4: Commit**
  ```bash
  git add backend/services/order_service.py backend/services/delivery_note_service.py backend/api/routers/orders.py backend/api/routers/delivery_notes.py
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "refactor: estrazione OrderService e DeliveryNoteService"
  ```

---

### Task 2: `InvoiceService` e `AccountingService` (Amministrazione e Finanza)

**Files:**
- Create: `backend/services/invoice_service.py`
- Create: `backend/services/accounting_service.py`
- Modify: `backend/api/routers/invoices.py`
- Modify: `backend/api/routers/accounting.py`
- Modify: `backend/api/routers/pos.py` (usa il posting automatico)

- [ ] **Step 1: Creare `backend/services/accounting_service.py`**
  - Spostare `create_journal_entry` (con check del bilanciamento `abs(tot_dare - tot_avere) > 0.001`), reportistica.
  - Spostare `auto_post_invoice_to_accounting` da `invoices.py` a `AccountingService`.

- [ ] **Step 2: Creare `backend/services/invoice_service.py`**
  - Spostare `calculate_installments`, `create_invoice_from_ddt`, `create_invoice_direct`, `create_credit_note_from_invoice`, `pay_installment`.

- [ ] **Step 3: Aggiornare i Router `invoices.py` e `accounting.py`**
  - I router si limiteranno a fare parse della request e chiamare i servizi.

- [ ] **Step 4: Verificare la test suite di amministrazione**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_invoices_installments.py tests/backend/test_credit_notes.py tests/backend/test_accounting.py tests/backend/test_accounting_causals_sync.py -v`

- [ ] **Step 5: Commit**
  ```bash
  git add backend/services/invoice_service.py backend/services/accounting_service.py backend/api/routers/
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "refactor: estrazione InvoiceService e AccountingService"
  ```

---

### Task 3: `PalletService`, `CmrService` e `WarehouseService` (Supply Chain Estesa)

**Files:**
- Create: `backend/services/pallet_service.py`
- Create: `backend/services/cmr_service.py`
- Create: `backend/services/warehouse_service.py`
- Modify: I rispettivi router.

- [ ] **Step 1: Creare `backend/services/pallet_service.py`**
  - Spostare `create_pallet_receipt`, `return_pallet_receipt`, `get_pallets_ledger`, `invoice_unreturned_pallets`.

- [ ] **Step 2: Creare `backend/services/cmr_service.py`**
  - Spostare `create_cmr_from_ddt` (hub Alessandria, impaginazione 21 righe), `create_cmr_manual`.

- [ ] **Step 3: Creare `backend/services/warehouse_service.py`**
  - Spostare calcolo giacenze `get_warehouse_stock`, calcolo lotti bio FEFO `get_fefo_suggestions` e logica `create_purchase`.

- [ ] **Step 4: Aggiornare i router e verificare i test**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_pallets_interchange.py tests/backend/test_cmr_export.py tests/backend/test_warehouse_fefo.py -v`

- [ ] **Step 5: Commit**
  ```bash
  git add backend/services/ backend/api/routers/
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "refactor: estrazione PalletService, CmrService e WarehouseService"
  ```

---

### Task 4: `PosSaleService` (Punto Vendita)

**Files:**
- Create: `backend/services/pos_sale_service.py`
- Modify: `backend/api/routers/pos.py`

- [ ] **Step 1: Creare `backend/services/pos_sale_service.py`**
  - Spostare `create_pos_sale`: Lookup lotti bio in FEFO automatico, stacco scontrino fiscale `PosDriverService`, inserimento automatico Corrispettivi `AccountingService`, Event Dispatching.

- [ ] **Step 2: Aggiornare `pos.py` e verificare**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_pos_bancom.py -v`

- [ ] **Step 3: Verifica Globale Test Suite Backend**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/ -q`

- [ ] **Step 4: Commit Finale Architettura Clean**
  ```bash
  git add backend/services/pos_sale_service.py backend/api/routers/pos.py
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "refactor: estrazione PosSaleService e completamento Clean Architecture"
  ```
