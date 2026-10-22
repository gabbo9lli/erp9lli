# Causali Contabili Operative (AccountingCausal), Allineamento Automatico Partita Doppia ed Event Bus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare l'anagrafica delle causali contabili operative (`AccountingCausal`) con mapping dinamico dei conti (Dare/Avere/IVA), associazione dichiarativa a `EventType` e allineamento automatico completo di Partita Doppia ed Event Bus all'emissione di fatture, incasso rate e note di credito.

**Architecture:** Modello relazionale `AccountingCausal` collegato a `Account`, estensione di `EventType` e `JournalEntry`. Seed delle causali operative standard (`VEND_FATT`, `VEND_NC`, `INCASSO_RATA`, `CORRISPETTIVO`, `ACQ_MERCI`, `PAGAM_FORN`). Automazione nel backend per la generazione sincronizzata di `JournalEntry` (a pareggio centesimale `Dare == Avere`) e emissione di `SystemEvent` (`EMISSIONE_FATTURA`, `INCASSO_RATA`). Console Quasar in `Accounting.vue` per consultazione e auto-compilazione prima nota.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, Alembic, PostgreSQL 15, Vue 3, Quasar 2.16, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-causali-contabili-allineamento-partita-doppia-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Quadratura Contabile Vincolante:** Tutte le registrazioni automatiche in Partita Doppia devono soddisfare `abs(totale_dare - totale_avere) <= 0.001`.
- **Nessun Codice Conto Cablato:** I conti da movimentare devono essere ricavati dinamicamente dall'anagrafica `AccountingCausal` collegata all'evento, con fallback sicuro sul piano dei conti.
- **Tracciabilità Integrata:** Ogni allineamento contabile automatico DEVE emettere contestualmente un evento su Event Bus (`dispatch_event`) con riferimento incrociato tra ID documento e ID scrittura contabile.

## Review Focus

1. **Persistenza e Relazioni Causali:** Creazione tabella `accounting_causal` con FK verso `account` e collegamenti a `event_type` e `journal_entry`.
2. **Seed Causali Operative Standard:** Popolamento automatico delle 6 causali standard e collegamento con i rispettivi `EventType`.
3. **Allineamento Automatico Fatture:** Creazione fattura genera `JournalEntry` (Dare Crediti, Avere Ricavi e IVA) ed evento `EMISSIONE_FATTURA`.
4. **Allineamento Automatico Incasso Rate:** Chiamata a `/api/installments/<id>/pay` genera `JournalEntry` (Dare Banca, Avere Crediti) ed evento `INCASSO_RATA`.
5. **Allineamento Automatico Note di Credito:** Creazione nota di credito genera `JournalEntry` di storno ed evento tracciato.

---

### Task 1: Modello `AccountingCausal`, Estensione `EventType`, `JournalEntry` e Migrazione Database

**Files:**
- Create: `backend/models/accounting_causal.py`
- Modify: `backend/models/event_type.py`
- Modify: `backend/models/journal_entry.py`
- Modify: `backend/models/__init__.py`
- Create: `tests/backend/test_accounting_causals_sync.py`

**Interfaces:**
- Produces: Modello `AccountingCausal`, colonna `accounting_causal_id` su `EventType`, colonna `causale_id` su `JournalEntry`.

- [ ] **Step 1: Scrivere test per la persistenza del modello `AccountingCausal` in `tests/backend/test_accounting_causals_sync.py`**
  ```python
  def test_accounting_causal_model_persistence(client):
      from models import db, Account, AccountingCausal, EventType, JournalEntry
      with client.application.app_context():
          acc_crediti = Account(codice="1101", nome="Crediti Clienti", tipo="attivo")
          acc_ricavi = Account(codice="4101", nome="Ricavi Vendite Bio", tipo="ricavi")
          acc_iva = Account(codice="2201", nome="Erario c/IVA a Debito", tipo="passivo")
          db.session.add_all([acc_crediti, acc_ricavi, acc_iva])
          db.session.commit()

          causal = AccountingCausal(
              codice="VEND_FATT",
              descrizione="Fattura di Vendita a Cliente",
              tipo_registro="vendite",
              conto_dare_id=acc_crediti.id,
              conto_avere_id=acc_ricavi.id,
              conto_iva_id=acc_iva.id
          )
          db.session.add(causal)
          db.session.commit()

          assert causal.id is not None
          assert causal.conto_dare.codice == "1101"
          assert causal.conto_avere.codice == "4101"
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_accounting_causals_sync.py -v`
  - Expected: FAIL (`ImportError: cannot import name 'AccountingCausal' from 'models'`).

- [ ] **Step 3: Creare `backend/models/accounting_causal.py`, estendere `event_type.py` e `journal_entry.py`, aggiornare `__init__.py`**
  - Implementare modello `AccountingCausal` con relazioni, campi e `to_dict()`.
  - Aggiungere `accounting_causal_id` su `EventType` e `causale_id` su `JournalEntry`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_accounting_causals_sync.py -v`
  - Expected: PASS.

- [ ] **Step 5: Eseguire la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add accounting causals and relationships" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Tabella `accounting_causal` creata e colonne aggiunte su PostgreSQL.

---

### Task 2: Seed delle Causali Contabili Standard e Collegamento EventType

**Files:**
- Modify: `backend/seed_accounting.py`
- Modify: `backend/services/event_dispatcher.py`
- Modify: `tests/backend/test_accounting_causals_sync.py`

**Interfaces:**
- Produces: `seed_default_accounting_causals()`, collegamento `accounting_causal_id` su `EventType`.

- [ ] **Step 1: Scrivere test per il seed delle causali standard in `tests/backend/test_accounting_causals_sync.py`**
  - `test_seed_accounting_causals_and_event_type_link`: verifica popolamento delle 6 causali e collegamento automatico a `EMISSIONE_FATTURA`, `INCASSO_RATA`, `CARICO_MERCI`.

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_accounting_causals_sync.py -k test_seed_accounting_causals -v`
  - Expected: FAIL.

- [ ] **Step 3: Implementare `seed_default_accounting_causals()` in `backend/seed_accounting.py` e collegare gli `EventType` in `backend/services/event_dispatcher.py`**
  - Seed delle 6 causali standard e mapping su `EventType`.

- [ ] **Step 4: Eseguire il test per verificare che passi (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_accounting_causals_sync.py -k test_seed_accounting_causals -v`
  - Expected: PASS.

---

### Task 3: Allineamento Automatico Partita Doppia ed Event Bus su Fatture, Rate e Note di Credito

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_accounting_causals_sync.py`

**Interfaces:**
- Consumes: Causali da DB, emissione fatture/rate/NC.
- Produces: `JournalEntry` automatica a pareggio centesimale, emissione `SystemEvent` con payload correlato, endpoint `/api/accounting/causals`.

- [ ] **Step 1: Scrivere test per l'allineamento automatico in `tests/backend/test_accounting_causals_sync.py`**
  - `test_auto_accounting_and_event_on_invoice_creation`: verifica che la creazione di una fattura crei `JournalEntry` bilanciata e registri l'evento `EMISSIONE_FATTURA` su Event Bus.
  - `test_auto_accounting_and_event_on_installment_pay`: verifica che l'incasso rata crei `JournalEntry` (Dare Banca, Avere Crediti) e registri l'evento `INCASSO_RATA`.
  - `test_auto_accounting_and_event_on_credit_note`: verifica che la nota di credito crei `JournalEntry` di storno e registri l'evento su Event Bus.

- [ ] **Step 2: Eseguire i test per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_accounting_causals_sync.py -k "test_auto_accounting" -v`
  - Expected: FAIL.

- [ ] **Step 3: Implementare gli allineamenti automatici e gli endpoint `/api/accounting/causals` in `backend/app.py`**
  - Invocazione automatica creazione `JournalEntry` ed emissione `dispatch_event` in `create_invoice`, `pay_installment`, `create_credit_note`.

- [ ] **Step 4: Eseguire tutti i test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_accounting_causals_sync.py -v`
  - Expected: PASS (100%).

---

### Task 4: Frontend Quasar in `Accounting.vue` per Causali Contabili e Pre-compilazione Prima Nota

**Files:**
- Modify: `frontend/src/components/Accounting.vue`
- Modify: `tests/frontend/Accounting.spec.js`

**Interfaces:**
- Consumes: `/api/accounting/causals`, `/api/accounting/accounts`.
- Produces: Scheda "Causali Contabili & Automatismi" e auto-compilazione conti nel dialog prima nota.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/Accounting.spec.js`**
  - Verifica presenza scheda "Causali Contabili" e rendering delle causali con relativi conti.

- [ ] **Step 2: Eseguire test per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/Accounting.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Aggiornare `frontend/src/components/Accounting.vue`**
  - Aggiungere tab "Causali Contabili & Automatismi".
  - Tabella con selezione conti Dare, Avere e IVA.
  - Selezione causale nel dialog "Nuova Registrazione" con auto-compilazione conti.

- [ ] **Step 4: Eseguire test frontend (GREEN)**
  - Run: `npm --prefix frontend run test ../tests/frontend/Accounting.spec.js`
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
  - Creazione fattura live via curl, verifica generazione automatica `JournalEntry` e presenza evento in `/api/events`.

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
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo causali contabili operative allineamento automatico partita doppia ed event bus"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
