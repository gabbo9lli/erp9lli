# Anagrafiche Core (Partner e Product) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare le anagrafiche cardine (Soggetti Commerciali `Partner` e Catalogo Articoli Biologici `Product`) ispirate a Gestionale ReteBio con modelli relazionali PostgreSQL, API REST Flask protette e maschere interattive Quasar in Vue 3.

**Architecture:** Modello polimorfico `Partner` (Clienti, Fornitori, Vettori con dati fiscali, SDI a 7 caratteri e PEC) e modello `Product` (categorie Fresco/Trasformato/Imballo, unità di misura, pesi, tracciabilità lotti biologici, marginalità e codice doganale NC). Esposti tramite API REST Flask con `@require_auth` e fruibili via componenti Quasar `<q-table>`.

**Tech Stack:** Python 3.11, Flask, SQLAlchemy, Alembic, PostgreSQL 15, Vue 3, Quasar 2.16, Vite, Pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-19-anagrafiche-core-retebio-design.md`

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare tutti i commit con `git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "..."` e autore `gabbo <gabbo9lli@gmail.com>`.
- **TDD:** Ogni nuova funzionalità (backend e frontend) deve essere preceduta da un test che fallisce (RED), seguito dall'implementazione minima per passare (GREEN).
- **Naming Conventions & Schema:** I modelli devono rispettare la convenzione di naming SQLAlchemy già presente in `models.py`.

## Review Focus

1. **Unicità Codice Articolo:** Tentativi di inserimento prodotti con lo stesso `codice` devono restituire 400 Bad Request.
2. **Validazione SDI & Fiscali Partner:** Il codice SDI deve essere gestito con default `'0000000'` e non deve generare eccezioni se non fornito.
3. **Filtri Parametrici:** Ricerca e filtro per `tipo` su `/api/partners` e per `categoria` su `/api/products` devono funzionare in modo combinabile.
4. **Protezione RBAC:** Modifiche e cancellazioni anagrafiche devono richiedere ruolo `'Admin'` (403 per utenti standard).
5. **Calcolo Margine Frontend:** Nel catalogo articoli la marginalità (`prezzo_vendita - prezzo_acquisto`) deve essere calcolata dinamicamente senza errori per valori nulli/zero.

---

### Task 1: Backend Models `Partner` e `Product` e Migrazione Database

**Files:**
- Modify: `backend/models.py`
- Create: `tests/backend/test_partners_products.py`

**Interfaces:**
- Produces: Classi SQLAlchemy `Partner` e `Product` con vincoli di integrità e convenzioni di naming.

- [ ] **Step 1: Scrivere test per la persistenza dei modelli in `tests/backend/test_partners_products.py`**
  ```python
  def test_partner_model_creation(client):
      from models import db, Partner
      with client.application.app_context():
          p = Partner(ragione_sociale="Azienda Agricola Bio", tipo="fornitore", partita_iva="IT12345678901")
          db.session.add(p)
          db.session.commit()
          assert p.id is not None
          assert p.codice_sdi == "0000000"

  def test_product_model_creation(client):
      from models import db, Product
      with client.application.app_context():
          prod = Product(codice="BIO-MELA", descrizione="Mele Golden Bio", categoria="fresco", prezzo_vendita=2.50, prezzo_acquisto=1.20)
          db.session.add(prod)
          db.session.commit()
          assert prod.id is not None
          assert prod.in_scadenza is False
  ```

- [ ] **Step 2: Eseguire il test per verificare che fallisca (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_partners_products.py -v`
  - Expected: FAIL (`ImportError: cannot import name 'Partner' from 'models'`).

- [ ] **Step 3: Implementare i modelli `Partner` e `Product` in `backend/models.py`**
  - Definire `Partner` con campi `ragione_sociale`, `tipo`, `partita_iva`, `codice_fiscale`, `indirizzo`, `cap`, `citta`, `provincia`, `nazione`, `codice_sdi`, `pec`, `istituto_certificatore`, `iban`, `condizioni_pagamento`, `attivo`.
  - Definire `Product` con campi `codice`, `descrizione`, `descrizione_en`, `categoria`, `unita_misura`, `peso_netto`, `peso_lordo`, `tara`, `in_scadenza`, `scorta_minima`, `prezzo_vendita`, `prezzo_acquisto`, `aliquota_iva`, `codice_nc`, `attivo`.

- [ ] **Step 4: Eseguire i test dei modelli (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_partners_products.py -v`
  - Expected: PASS.

- [ ] **Step 5: Applicare la migrazione Alembic nel container database**
  - Run: `docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db migrate -m "add partner and product models" && docker compose -f docker-compose.yaml -f docker-compose.override.yaml exec backend flask db upgrade`
  - Expected: Migrazione generata ed applicata con successo.

---

### Task 2: Backend REST APIs (`/api/partners` & `/api/products`) con RBAC e Filtri

**Files:**
- Modify: `backend/app.py`
- Modify: `tests/backend/test_partners_products.py`

**Interfaces:**
- Consumes: Header di identità `X-Forwarded-*`, query parameters (`tipo`, `categoria`, `search`).
- Produces: Endpoint REST completi `/api/partners` e `/api/products`.

- [ ] **Step 1: Scrivere test API in `tests/backend/test_partners_products.py`**
  - `test_api_partners_crud`: creazione, elenco con filtro per tipo, modifica e cancellazione.
  - `test_api_products_crud`: creazione, verifica unicità codice (errore 400 su duplicato), elenco con filtro per categoria.
  - `test_api_rbac_partner_product`: verifica che modifiche richiedano ruolo `'Admin'` (403 per `'User'`).

- [ ] **Step 2: Eseguire test API per verificare che falliscano (RED)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_partners_products.py -v`
  - Expected: FAIL (404 / endpoints not found).

- [ ] **Step 3: Implementare gli endpoint in `backend/app.py`**
  - Rotte `/api/partners` (GET, POST) e `/api/partners/<int:id>` (PUT, DELETE).
  - Rotte `/api/products` (GET, POST) e `/api/products/<int:id>` (PUT, DELETE).
  - Gestione filtri: `search` (ricerca ILIKE), `tipo`, `categoria`.
  - Protezione con `@require_auth()` per GET e `@require_auth(roles=['Admin'])` per POST, PUT, DELETE.

- [ ] **Step 4: Eseguire la suite di test backend (GREEN)**
  - Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/ -v`
  - Expected: 100% test superati (tutti i test di test_api.py, test_forward_auth.py e test_partners_products.py).

---

### Task 3: Frontend Views (`PartnerManagement.vue` e `ProductCatalog.vue`) e Routing

**Files:**
- Create: `frontend/src/components/PartnerManagement.vue`
- Create: `frontend/src/components/ProductCatalog.vue`
- Modify: `frontend/src/router.js`
- Modify: `frontend/src/App.vue`
- Create: `tests/frontend/Partners.spec.js`
- Create: `tests/frontend/Products.spec.js`

**Interfaces:**
- Consumes: Endpoint backend `/api/partners` e `/api/products`.
- Produces: Maschere responsive Quasar integrate nel router applicativo e nella navbar.

- [ ] **Step 1: Scrivere i test frontend in `tests/frontend/Partners.spec.js` e `tests/frontend/Products.spec.js`**
  - `Partners.spec.js`: verifica montaggio tabella partner e presenza filtri.
  - `Products.spec.js`: verifica montaggio catalogo prodotti e calcolo margine commerciale.

- [ ] **Step 2: Eseguire i test frontend per verificare che falliscano (RED)**
  - Run: `npm --prefix frontend run test ../tests/frontend/Partners.spec.js ../tests/frontend/Products.spec.js`
  - Expected: FAIL.

- [ ] **Step 3: Creare `frontend/src/components/PartnerManagement.vue`**
  - Tabella `<q-table>` Quasar con tab rapidi (*Tutti*, *Clienti*, *Fornitori*, *Vettori*).
  - Dialog modale `<q-dialog>` per inserimento e modifica anagrafica.

- [ ] **Step 4: Creare `frontend/src/components/ProductCatalog.vue`**
  - Tabella `<q-table>` con chip visivi (*Fresco*, *Trasformato*, *Bio/Scadenza*).
  - Calcolo del margine lordo e percentuale di ricarico.
  - Dialog modale per inserimento e modifica scheda articolo.

- [ ] **Step 5: Aggiornare `frontend/src/router.js` e `frontend/src/App.vue`**
  - Aggiungere rotte `/partners` e `/products` con `meta: { requiresAuth: true }`.
  - Aggiungere i link "Articoli" e "Soggetti" nella barra di navigazione `App.vue`.

- [ ] **Step 6: Eseguire tutti i test frontend (GREEN)**
  - Run: `npm --prefix frontend run test`
  - Expected: 100% test superati (tutti gli spec frontend).

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
  - Invocare `curl -s http://localhost:5000/api/partners` e `curl -s http://localhost:5000/api/products` verificando risposta HTTP 200.

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
  git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat: anagrafiche core partner e product ispirate a gestionale retebio"
  ```

- [ ] **Step 3: Verifica stato git**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
