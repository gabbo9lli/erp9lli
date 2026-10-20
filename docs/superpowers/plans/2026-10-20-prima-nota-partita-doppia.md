# Prima Nota, Partita Doppia e Documenti Contabili Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare il modulo di Contabilità Generale a Partita Doppia con Piano dei Conti (`Account`), Scritture di Prima Nota a pareggio bilanciato (`JournalEntry`, `JournalItem`), e motore di visualizzazione ed export (JSON/CSV) per Libro Giornale, Schede Mastro e Bilancio di Verifica.

**Architecture:** Modelli relazionali PostgreSQL per conti e registrazioni con vincolo atomico `SUM(dare) == SUM(avere)`. API REST Flask con serializzatore per formato JSON e generatore streaming CSV per gli studi professionali. Maschera Quasar responsive con form di scrittura a controllo dinamico di bilanciamento e visualizzatori documentali.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, Alembic, PostgreSQL 15, Vue 3, Quasar 2.16, Vite, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-20-prima-nota-partita-doppia-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Vincolo Inviolabile di Partita Doppia:** Qualsiasi tentativo di salvare una scrittura con `abs(totale_dare - totale_avere) > 0.001` deve essere categoricamente respinto con HTTP 400 Bad Request.

## Review Focus

1. **Rifiuto Sbilancio Contabile:** Registrazioni con Dare diverso da Avere devono restituire 400 e non persistere alcuna riga.
2. **Numerazione Progressiva Libro Giornale:** Il numero di prima nota deve incrementare per anno (`PN-2026-0001`, `PN-2026-0002`).
3. **Calcolo Saldo Progressivo Mastro:** Nella scheda mastro, per i conti dell'attivo/costi il saldo aumenta in Dare e diminuisce in Avere; per passivo/ricavi aumenta in Avere.
4. **Pareggio Bilancio di Verifica:** Il totale complessivo dei movimenti Dare deve pareggiare esattamente il totale dei movimenti Avere nel prospetto di bilancio.
5. **Conformità Export CSV:** L'export CSV deve includere intestazioni corrette, encoding UTF-8 e formattazione decimale idonea a Excel.

---

### Task 1: Backend Models `Account`, `JournalEntry`, `JournalItem` e Seed Piano dei Conti

**Files:**
- Modify: `backend/models.py`
- Create: `backend/seed_accounting.py`
- Create: `tests/backend/test_accounting.py`

**Interfaces:**
- Produces: Classi SQLAlchemy `Account`, `JournalEntry`, `JournalItem`, script `seed_accounting.py`.

- [ ] **Step 1: Scrivere test per la persistenza dei modelli e seed in `tests/backend/test_accounting.py`**
  ```python
  def test_account_and_journal_models(client):
      from models import db, Account, JournalEntry, JournalItem
      from datetime import date
      with client.application.app_context():
          acc_cassa = Account(codice="1001", nome="Cassa Contanti", tipo="attivo")
          acc_banca = Account(codice="1002", nome="Banca c/c", tipo="attivo")
          db.session.add_all([acc_cassa, acc_banca])
          db.session.commit()

          entry = JournalEntry(
              numero=1,
              anno=2026,
              numero_completo="PN-2026-0001",
              data_registrazione=date.today(),
              data_competenza=date.today(),
              causale="Versamento contanti in banca",
              totale_dare=500.0,
              totale_avere=500.0,
              stato="confermata"
          )
          db.session.add(entry)
          db.session.commit()

          item1 = JournalItem(journal_entry_id=entry.id, account_id=acc_banca.id, dare=500.0, avere=0.0)
          item2 = JournalItem(journal_entry_id=entry.id, account_id=acc_cassa.id, dare=0.0, avere=500.0)
          db.session.add_all([item1, item2])
          db.session.commit()

          assert entry.id is not None
          assert len(entry.items) == 2
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_accounting.py -v`
  - Expected: FAIL (`ImportError: cannot import name 'Account' from 'models'`).

- [ ] **Step 3: Implementare i modelli in `backend/models.py` e creare `backend/seed_accounting.py`**
  - In `models.py`: definire `Account`, `JournalEntry` e `JournalItem` con vincoli e metodi `to_dict()`.
  - In `seed_accounting.py`: definire `seed_chart_of_accounts()` per inserire i conti standard italiani (1001, 1002, 1101, 2001, 2201, 2202, 3001, 4101, 5101, 5201, 5301).

- [ ] **Step 4: Eseguire i test dei modelli (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_accounting.py -v`
  - Expected: PASS.

- [ ] **Step 5: Applicare la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add accounting models" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Nuove tabelle create con successo su PostgreSQL.

---

### Task 2: Backend REST APIs (Prima Nota a Pareggio e Motore Report con Export CSV)

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_accounting.py`

**Interfaces:**
- Consumes: Scritture di prima nota bilanciate, parametri di filtro date e conti.
- Produces: Endpoint `/api/accounting/accounts`, `/api/accounting/entries`, `/api/accounting/reports/libro-giornale`, `/api/accounting/reports/mastro`, `/api/accounting/reports/bilancio-verifica`.

- [ ] **Step 1: Scrivere test API in `tests/backend/test_accounting.py`**
  - `test_unbalanced_entry_rejected`: scrittura con Dare != Avere respinta con errore 400.
  - `test_balanced_entry_creation`: scrittura a pareggio accettata con assegnazione automatica `PN-YYYY-XXXX`.
  - `test_libro_giornale_report_json_and_csv`: verifica estrazione cronologica e formato CSV con header `Content-Type: text/csv`.
  - `test_mastro_running_balance`: verifica calcolo corretto del saldo progressivo.
  - `test_bilancio_di_verifica_balance`: verifica quadratura pareggio bilancio.

- [ ] **Step 2: Eseguire test API per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_accounting.py -v`
  - Expected: FAIL (404 / endpoints not found).

- [ ] **Step 3: Implementare gli endpoint contabili in `backend/app.py`**
  - CRUD conti contabili `/api/accounting/accounts`.
  - Creazione ed elenco scritture `/api/accounting/entries` con controllo bloccante `abs(sum(dare) - sum(avere)) <= 0.001`.
  - Report Libro Giornale `/api/accounting/reports/libro-giornale` (con generatore CSV).
  - Report Scheda Mastro `/api/accounting/reports/mastro` (con calcolo saldo progressivo e generatore CSV).
  - Report Bilancio di Verifica `/api/accounting/reports/bilancio-verifica` (con totale pareggio e generatore CSV).

- [ ] **Step 4: Eseguire la suite di test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/ -v`
  - Expected: 100% test superati.

---

### Task 3: Frontend Views (`Accounting.vue`) e Routing

**Files:**
- Create: `frontend/src/components/Accounting.vue`
- Modify: `frontend/src/router.js`
- Modify: `frontend/src/App.vue`
- Create: `tests/frontend/Accounting.spec.js`

**Interfaces:**
- Consumes: API contabili `/api/accounting/...`.
- Produces: Console Quasar a 5 schede (Prima Nota, Libro Giornale, Schede Mastro, Bilancio di Verifica, Piano dei Conti) con indicatore di bilanciamento in tempo reale e pulsanti di download CSV.

- [ ] **Step 1: Scrivere test frontend in `tests/frontend/Accounting.spec.js`**
  - Verifica caricamento console contabilità, presenza schede e pulsanti di export CSV.

- [ ] **Step 2: Eseguire test frontend per verificare che fallisca (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/Accounting.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Creare `frontend/src/components/Accounting.vue`**
  - Tab 1: Prima Nota (tabella registrazioni + dialog con righe dinamiche Dare/Avere e badge verde/rosso di bilanciamento).
  - Tab 2: Libro Giornale (visualizzazione e download CSV).
  - Tab 3: Schede Mastro (selettore conto, estratto conto con saldi progressivi e download CSV).
  - Tab 4: Bilancio di Verifica (tabella prospetto con quadratura a fondo pagina e download CSV).
  - Tab 5: Piano dei Conti.

- [ ] **Step 4: Aggiornare `frontend/src/router.js` e `frontend/src/App.vue`**
  - Aggiungere rotta protetta `/accounting`.
  - Aggiungere il link "Contabilità" nella navbar di `App.vue`.

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
  - Eseguire il seed dei conti nel container live (`python seed_accounting.py`).
  - Creare una registrazione live a pareggio via curl e scaricare il CSV del Libro Giornale verificando risposta HTTP 200.

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
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: modulo prima nota partita doppia e reporting civilistico con export csv"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
