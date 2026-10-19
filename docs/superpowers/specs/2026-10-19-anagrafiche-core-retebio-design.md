# Specifica Architetturale: Anagrafiche Core (Partner e Product) per erp9lli

## 1. Obiettivo e Contesto

Integrare nel gestionale **`erp9lli`** le anagrafiche fondamentali ispirate alle regole di business e al modello dati di **`GestionaleReteBio2026`** (`T_Clienti` e `T_ART`), superando i vincoli dell'architettura desktop legacy Microsoft Access:
- **Modello Polimorfico Soggetti (`Partner`)**: unificazione di Clienti, Fornitori e Vettori in un'unica entità relazionale con gestione fiscale italiana ed estera (Codice Destinatario SDI, PEC, P.IVA/CF, certificatore biologico).
- **Catalogo Articoli Biologici (`Product`)**: gestione differenziata Fresco vs Trasformati vs Imballi, pesi netti/lordi, vincolo di tracciabilità biologica (*In Scadenza* / lotti), prezzi acquisto/vendita con marginalità e codici doganali per l'export (*Codice NC*).
- **Backend API REST**: endpoint protetti in Flask (`@require_auth`) con filtri parametrici e ricerca full-text su PostgreSQL.
- **Frontend SPA Quasar**: due maschere moderne, veloci e responsive (`PartnerManagement.vue` e `ProductCatalog.vue`) integrate nella navigazione principale.
- **Suite di Test (TDD)**: copertura completa con Pytest per le API e Vitest per le viste frontend.

---

## 2. Modello Dati Relazionale (`backend/models.py`)

### 2.1 Tabella `partner` (Anagrafica Soggetti Commerciali)
Rappresenta ogni soggetto terzo che intrattiene relazioni commerciali con l'azienda.

| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `ragione_sociale` | String(150) | Not Null, Index | Denominazione sociale o nome/cognome |
| `tipo` | String(20) | Not Null, default `'cliente'` | `'cliente'`, `'fornitore'`, `'vettore'`, `'entrambi'` |
| `partita_iva` | String(20) | Nullable | P.IVA (validazione formato per IT) |
| `codice_fiscale` | String(20) | Nullable | Codice Fiscale |
| `indirizzo` | String(200) | Nullable | Via e numero civico |
| `cap` | String(10) | Nullable | Codice Avviamento Postale |
| `citta` | String(100) | Nullable | Comune |
| `provincia` | String(10) | Nullable | Sigla provincia (es. RE, MO, AL) |
| `nazione` | String(5) | Not Null, default `'IT'` | Codice ISO 3166-1 alpha-2 |
| `codice_sdi` | String(7) | Not Null, default `'0000000'` | Codice destinatario Fattura Elettronica SDI |
| `pec` | String(120) | Nullable | Indirizzo PEC per fatturazione |
| `istituto_certificatore`| String(100) | Nullable | Ente certificatore bio (es. ICEA, CCPB, Bioagricert) |
| `iban` | String(35) | Nullable | Coordinate bancarie IBAN |
| `condizioni_pagamento` | String(50) | Not Null, default `'30gg fm'` | Condizioni (es. `30gg fm`, `60gg fm`, `bonifico`) |
| `attivo` | Boolean | Not Null, default `True` | Flag abilitazione anagrafica |

### 2.2 Tabella `product` (Catalogo Prodotti)
Rappresenta gli articoli commercializzati o movimentati a magazzino.

| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `codice` | String(50) | Not Null, Unique, Index | Codice articolo (es. `ART-001`, `BIO-MELA`) |
| `descrizione` | String(200) | Not Null | Descrizione commerciale in lingua italiana |
| `descrizione_en` | String(200) | Nullable | Descrizione in inglese per export/CMR |
| `categoria` | String(50) | Not Null, default `'fresco'` | `'fresco'`, `'trasformato'`, `'imballo'` |
| `unita_misura` | String(10) | Not Null, default `'KG'` | UdM principale (`KG`, `PZ`, `LT`) |
| `peso_netto` | Float | Not Null, default `0.0` | Peso netto unitario in Kg |
| `peso_lordo` | Float | Not Null, default `0.0` | Peso lordo unitario in Kg |
| `tara` | Float | Not Null, default `0.0` | Tara imballo unitario |
| `in_scadenza` | Boolean | Not Null, default `False` | Se True richiede lotto fornitore e scadenza obbligatori |
| `scorta_minima` | Float | Not Null, default `0.0` | Soglia di riordino magazzino |
| `prezzo_vendita` | Float | Not Null, default `0.0` | Prezzo unitario di vendita (listino base) |
| `prezzo_acquisto` | Float | Not Null, default `0.0` | Costo unitario medio o d'acquisto |
| `aliquota_iva` | Integer | Not Null, default `4` | Aliquota IVA applicata (es. 4, 10, 22) |
| `codice_nc` | String(20) | Nullable | Nomenclatura Combinata doganale per export UE/extra-UE |
| `attivo` | Boolean | Not Null, default `True` | Flag articolo a listino attivo |

---

## 3. Specifiche API REST (`backend/app.py`)

### 3.1 Endpoint Partner (`/api/partners`)
- `GET /api/partners`: Elenco paginato/filtrato.
  - Parametri query: `tipo` (cliente, fornitore, vettore), `search` (cerca in ragione sociale, P.IVA, città), `attivo` (true/false).
  - Risposta `200 OK`: `[{ id, ragione_sociale, tipo, partita_iva, citta, codice_sdi, ... }]`.
- `POST /api/partners`: Creazione nuovo partner. Richiede `@require_auth(roles=['Admin'])`.
- `PUT /api/partners/<int:id>`: Modifica partner esistente. Richiede `@require_auth(roles=['Admin'])`.
- `DELETE /api/partners/<int:id>`: Disattivazione o eliminazione fisica se senza documenti collegati. Richiede `@require_auth(roles=['Admin'])`.

### 3.2 Endpoint Prodotti (`/api/products`)
- `GET /api/products`: Catalogo articoli.
  - Parametri query: `categoria` (fresco, trasformato, imballo), `search` (codice o descrizione), `in_scadenza` (true/false).
  - Risposta `200 OK`: `[{ id, codice, descrizione, categoria, prezzo_vendita, prezzo_acquisto, in_scadenza, ... }]`.
- `POST /api/products`: Creazione nuovo prodotto. Validazione unicità codice. Richiede `@require_auth(roles=['Admin'])`.
- `PUT /api/products/<int:id>`: Modifica anagrafica prodotto. Richiede `@require_auth(roles=['Admin'])`.
- `DELETE /api/products/<int:id>`: Disattivazione prodotto. Richiede `@require_auth(roles=['Admin'])`.

---

## 4. Specifiche Interfaccia Utente Quasar (`frontend/src/`)

### 4.1 Componente `PartnerManagement.vue`
- Tabella `<q-table>` reattiva con filtri veloci per tipo (*Tutti*, *Clienti*, *Fornitori*, *Vettori*).
- Campo di ricerca full-text istantanea.
- Badge identificativi per tipo di soggetto e certificazione biologica.
- Dialog modale `<q-dialog>` con validazione per inserimento/modifica:
  - Tab *Anagrafica & Sede*: Ragione sociale, P.IVA, CF, indirizzo, CAP, città, provincia.
  - Tab *Dati Fiscali & SDI*: Codice SDI (controllo 7 caratteri), PEC, condizioni di pagamento, IBAN, istituto bio.

### 4.2 Componente `ProductCatalog.vue`
- Tabella `<q-table>` con ricerca per codice e descrizione.
- Chip visivi per categoria:
  - *Fresco*: chip verde (`positive`).
  - *Trasformato*: chip arancione (`warning`).
  - *Imballo*: chip blu (`info`).
  - *Bio / In Scadenza*: icona e badge dedicato per tracciabilità lotti.
- Visualizzazione economica con calcolo dinamico della marginalità:
  - Prezzo di vendita, Prezzo di acquisto, Margine lordo (€) e Ricarico (%).
- Dialog modale per creazione/modifica scheda tecnica articolo.

### 4.3 Navigazione Principale (`App.vue` & `router.js`)
- Nuove rotte con guardia di autenticazione:
  - `/products`: Catalogo Prodotti.
  - `/partners`: Anagrafica Soggetti.
- Aggiunta dei link nella barra di navigazione superiore `DevPortal`.

---

## 5. Strategia di Test Automatizzati

### 5.1 Test Backend (`tests/backend/test_partners_products.py`)
1. **Partner**:
   - `test_create_partner`: creazione con successo con campi fiscali e SDI.
   - `test_filter_partners_by_type`: verifica filtri per cliente vs fornitore.
   - `test_update_partner`: modifica anagrafica.
   - `test_rbac_partner_forbidden_for_user`: utenti standard non possono creare/modificare (403).
2. **Product**:
   - `test_create_product`: creazione con campi bio, categoria e prezzi.
   - `test_product_unique_code_constraint`: codice duplicato respinto con errore 400.
   - `test_filter_products_by_category`: filtro per `fresco` e `in_scadenza`.
   - `test_update_product_pricing`: aggiornamento listini.

### 5.2 Test Frontend (`tests/frontend/`)
1. **`tests/frontend/Partners.spec.js`**:
   - Verifica caricamento dati tabella partner e cambio tab filtri.
2. **`tests/frontend/Products.spec.js`**:
   - Verifica rendering tabella catalogo e calcolo margine commerciale.

---

## 6. Piano di Migrazione Database
- Creazione della migrazione Alembic: `flask db migrate -m "add partner and product models"`.
- Applicazione della migrazione: `flask db upgrade`.
