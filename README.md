# ERP9lli - Gestionale Integrato Filiera Ortofrutticola Biologica (ReteBio)

[![Backend Tests](https://img.shields.io/badge/pytest-94%20passed-brightgreen.svg)](tests/backend/)
[![Frontend Tests](https://img.shields.io/badge/vitest-25%20passed-brightgreen.svg)](tests/frontend/)
[![Architecture](https://img.shields.io/badge/stack-Vue3%20%7C%20FastAPI%20%7C%20PostgreSQL%20%7C%20Redis-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

**`erp9lli`** è una piattaforma ERP modulare containerizzata progettata per la gestione completa della supply chain, della logistica e della contabilità fiscale delle cooperative e aziende agricole ortofrutticole biologiche (aderenti agli standard di **ReteBio**).

Il sistema copre l'intero ciclo operativo: dalla ricezione ordini multicanale (diretto, vendita al banco e webhook e-commerce) all'entrata merci con tracciabilità lotti biologici e FEFO, bollettazione DDT sequenziale, spedizioni internazionali CMR, gestione interscambio pallet ai sensi della Legge 182/2025, fatturazione elettronica SDI (tracciato FPR12 FatturaPA v1.2.2), fino alla contabilità generale a partita doppia con allineamento automatico guidato da causali contabili operative.

---

## 🏛️ Architettura di Sistema

```
                  ┌────────────────────────────────────────────────────────┐
                  │          Reverse Proxy TLS / Traefik v3                │
                  │   (oauth2-proxy / OIDC Forward Auth SSO su /api/me)    │
                  └───────────────────────────┬────────────────────────────┘
                                              │
                     ┌────────────────────────┴────────────────────────┐
                     ▼                                                 ▼
        ┌─────────────────────────┐                       ┌─────────────────────────┐
        │   Frontend SPA (Vite)   │                       │   Backend API (ASGI)    │
        │   Vue 3 + Quasar v2.16  │                       │   FastAPI + Uvicorn     │
        │   Porta Host: 5173      │                       │   Porta Host: 5000      │
        └─────────────────────────┘                       └────────────┬────────────┘
                                                                       │
                                           ┌───────────────────────────┼───────────────────────────┐
                                           ▼                           ▼                           ▼
                              ┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
                              │  PostgreSQL 15 (RDBMS)  │ │   Redis 7 (Event Bus)   │ │  RQ Background Workers  │
                              │  29 Modelli Normalizzati│ │   4 Code Multiple (RQ)  │ │ critical | emails       │
                              │  Porta Host: 5432       │ │   Porta Host: 6379      │ │ batch    | default      │
                              └─────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘
```

### Componenti Chiave
- **Frontend SPA:** Vue 3 (Composition API, `<script setup>`), Quasar Framework 2.16, Pinia, Axios, Vitest.
- **Backend API:** Python 3.11, FastAPI con Uvicorn, Dependency Injection (`Depends(get_db)`), validazione Pydantic v2, SQLAlchemy 2.0 (DeclarativeBase), Alembic, Pytest.
- **Database Relazionale:** PostgreSQL 15 con modelli disaccoppiati in `backend/models/` (un file per tabella).
- **Asincronismo & Code Multiple:** Redis 7 alpine + Redis Queue (RQ) con catalogo dichiarativo degli eventi.
- **WebSockets:** WebSockets nativi asincroni di FastAPI (`/ws`).
- **Sicurezza:** Decoratore e dependency `require_auth(roles=None)` basati su header federati (`X-Forwarded-Email`, `X-Forwarded-Groups`) con fallback locale trasparente in ambiente di sviluppo.

---

## 📦 Moduli Funzionali Realizzati

### 1. 🛡️ Autenticazione & Sicurezza OIDC
- Integrazione Forward Auth / oauth2-proxy con estrazione identità utente da header HTTP;
- Auto-provisioning automatico degli utenti al primo accesso e mappatura ruoli RBAC (`Admin` vs `User`).

### 2. 🧩 Architettura Modulare a Pacchetti (`ENABLED_MODULES`)
- Feature flagging centralizzato via variabile d'ambiente `ENABLED_MODULES` (supporta `all` o lista comma-separated: `anagrafiche,orders,delivery_notes,invoicing,accounting,warehouse,pallets,cmr,pos,ecommerce`).

### 3. 👥 Anagrafiche Core & Catalogo Biologico ReteBio
- Gestione Anagrafiche Partner (`cliente`, `fornitore`, `vettore`, `entrambi`) con codice SDI, PEC, IBAN;
- Anagrafica Prodotti ortofrutticoli biologici con deperibilità `in_scadenza`, unità di misura (KG/PZ/COLLO), calcolo automatico margini/ricarico e codice doganale NC;
- Script di caricamento dati standard ReteBio: `python backend/seed_retebio.py`.

### 4. 🛒 Gestione Ordini Clienti
- Numerazione sequenziale per anno solare (`ORD-YYYY-XXXX`);
- Righe ordine a sequenze numeriche a passi di 5 (`5, 10, 15, 20...`);
- Stato avanzamento evasione ordini (`aperto`, `in_lavorazione`, `chiuso`) ed evasione diretta in Bolla DDT.

### 5. 🚚 Bollettazione DDT & Tracciabilità Lotti FEFO
- Numerazione sequenziale bloccante `DDT-YYYY-XXXX`;
- **Vincolo Biologico Obbligatorio:** Se il prodotto ha `in_scadenza == True`, il sistema impone obbligatoriamente `lotto` e `data_scadenza` (HTTP 400 bloccante);
- Algoritmo di scarico giacenze progressive con suggerimento **FEFO** (*First Expired, First Out*);
- Immutabilità post-conferma per garantire l'integrità fiscale.

### 6. 📥 Ciclo Passivo: Entrata Merci Fornitori
- Registrazione bolle di carico fornitore con tracciabilità lotti bio e date di scadenza;
- Calcolo automatico delle giacenze progressive e disponibilità residue per articolo e lotto.

### 7. 🔄 Interscambio Pallet a Rendiconto (Legge 182/2025)
- Emissione Buoni Pallet sequenziali `BP-YYYY-XXXX` con data di scadenza legale a 60 giorni;
- Partitario saldi Dare/Avere per partner e tipologia di pallet (EPAL, CHEP, IFCO, CPR);
- Fatturazione automatica dei pallet non restituiti con dicitura **Reverse Charge art. 74 c. 7/8 DPR 633/72** e natura SDI `N6.7`.

### 8. 🌍 Spedizioni Internazionali: Lettera di Vettura CMR Export
- Generazione documento CMR standard a 24 caselle numerate secondo convenzione internazionale;
- Regola automatica **Hub Alessandria** per vettore `LD TRASPORTI`;
- Regola impaginazione doganale: massimo 21 righe per casella 6-12 con emissione automatica allegato continuativo se superate.

### 9. 🧾 Fatturazione Differita/Immediata & Scadenzario Rate
- Fatturazione immediata (TD01) e differita da DDT confermati (TD24) con serie `FT-YYYY-XXXX`;
- Generazione automatica scadenze rate con quadratura centesimale sull'ultima rata per importi dispari;
- Incasso rate con registrazione automatica e chiusura di stato della fattura.

### 10. 🏛️ Fatturazione Elettronica SDI (Tracciato FPR12 / FatturaPA v1.2.2)
- Generazione on-demand del file XML conforme allo schema ufficiale dell'Agenzia delle Entrate;
- Valorizzazione automatica blocchi `<DatiDDT>` (con numero e data DDT) e `<DatiBeniServizi>`;
- Mappatura codici natura IVA (`N6.7` per Reverse Charge pallet, `N3.2` per esportazioni non imponibili, `N4` per esenti);
- Validazione sintattica XSD e download diretto dell'XML da interfaccia utente.

### 11. 🔄 Note di Credito TD04 & Resi Merci
- Serie numerica dedicata `NC-YYYY-XXXX`;
- Storno totale o parziale di fatture di vendita con valorizzazione automatica del blocco `<DatiFattureCollegate>`;
- Compensazione automatica sulle rate aperte del cliente e reintegro opzionale delle giacenze di magazzino.

### 12. 📊 Contabilità Generale a Partita Doppia
- Piano dei Conti conforme alla IV Direttiva CEE (Attivo, Passivo, Costi, Ricavi);
- Scritture contabili con quadratura obbligatoria `|Dare - Avere| <= 0.001` (HTTP 400 in caso di sbilancio);
- Registrazione Libro Giornale, Mastrini di Conto con saldo progressivo;
- Bilancio di Verifica a 4 colonne con quadratura saldi ed esportazione ufficiale in formato CSV.

### 13. ⚙️ Causali Contabili Operative (`AccountingCausal`) & Allineamento Automatico
- Anagrafica causali standard (`VEND_FATT`, `VEND_NC`, `INCASSO_RATA`, `CORRISPETTIVO`, `ACQ_MERCI`, `PAGAM_FORN`);
- **Nessun conto hardcoded:** la contabilizzazione di fatture, rate, note di credito e corrispettivi avviene dinamicamente leggendo le causali operative;
- Allineamento automatico completo di tutte le transazioni aziendali alla Partita Doppia.

### 14. 📡 Event Bus & Code Multiple Redis Queue (RQ)
- Canali dedicati (`AUDIT`, `EMAIL`, `NOTIFICA`, `WEBHOOK`, `BATCH`) e categorie logico-funzionali;
- Catalogo dichiarativo `EventType` con policy di esecuzione **Sincrono** o **Asincrono** configurabile da UI;
- Routing automatico su 4 code Redis separate:
  - `critical`: notifiche di sistema urgenti;
  - `emails`: invio fatture e solleciti;
  - `batch`: elaborazioni massive;
  - `default`: operazioni ordinarie;
- Cruscotto Activity Center in Quasar per monitorare code, task pendenti e audit trail.

### 15. 🏷️ Vendita al Banco / Cassa Rapida (`BancoM` / POS)
- Interfaccia touch screen ottimizzata Quasar (`BancoM.vue`);
- Driver registratore telematico pluggabile via factory pattern (`simulator`, `epson_epos_http`, `custom_tcp`);
- Calcolo automatico resto e tastierino banconote veloci (€5..€50);
- Generazione anteprima scontrino termico da 80mm conforme alle specifiche RT.

### 16. 🏷️ Stampa Etichette Barcode Termiche (`BarcodeLabelService`)
- Generatore vettoriale SVG nativo per codici a barre Code 128 (senza dipendenze native esterne);
- Generatore comandi Zebra ZPL II a 203 DPI con supporto internazionalizzazione UTF-8 (`^CI28`);
- Layout standard logistica ortofrutticola:
  - **Etichetta Bancale (100×150 mm):** dicitura biologica, organismo di controllo, lotto, peso netto/lordo, tara pallet;
  - **Etichetta Collo (50×30 mm):** identificativo unità di vendita, scadenza, codice a barre compatto;
- Dialog di anteprima, navigazione multi-etichetta e download/copia ZPL integrato in DDT e Anagrafica Articoli.

### 17. 🌐 Connettore & Sincronizzazione E-Commerce (Spree Commerce API)
- **Ricezione Ordini Webhook (`POST /api/ecommerce/webhook/orders`)**:
  - Endpoint protetto da token segreto (`X-Ecommerce-Secret`);
  - Parsing formato ordini Spree Commerce / Shop JSON;
  - Auto-provisioning o lookup del cliente (`Partner`);
  - Creazione ordine con sequenze a step 5 e stato `confermato`, pronto per evasione a DDT;
  - **Idempotenza Garantita:** gestione duplicati con risposta 200 OK senza creazione di record ridondanti;
- **Feed Giacenze in Tempo Reale (`GET /api/ecommerce/sync/stock`)**:
  - Calcolo disponibilità effettive (carichi meno scarichi DDT e vendite banco) esportabile in JSON;
- **Audit Sincronizzazione:** tracciamento chiamate su modello `EcommerceSyncLog` ed emissione evento `WEBHOOK` su Event Bus.

---

## 🚀 Avvio e Configurazione

### Prerequisiti
- Docker e Docker Compose installati sul sistema host.
- Python 3.11 con `uv` (per l'esecuzione opzionale dei test in locale).
- Node.js 18+ con `npm` (per il frontend).

### Avvio in Ambiente di Sviluppo
```bash
# Avvio di tutti i container (PostgreSQL, Redis, FastAPI Backend, Vite Dev Server)
docker compose -f docker-compose.yaml -f docker-compose.override.yaml up --build -d

# Visualizzazione log
docker compose logs -f
```

### Avvio in Ambiente di Produzione (con Proxy Nginx)
```bash
docker compose -f docker-compose.yaml -f docker-compose.prod.yaml up --build -d
```

### Inizializzazione Database & Seed
```bash
# Esecuzione migrazioni Alembic
docker compose exec backend alembic upgrade head

# Caricamento causali contabili operative standard CEE
docker compose exec backend python seed_accounting.py

# Caricamento anagrafiche partner e prodotti biologici ReteBio
docker compose exec backend python seed_retebio.py
```

---

## 🧪 Esecuzione Suite di Test Automatizzati (TDD)

Il progetto è stato sviluppato con metodologia **Test-Driven Development (TDD)** rigorosa.

### Test Backend (Pytest con FastAPI TestClient)
```bash
# Esecuzione completa di tutti i 94 test backend
uv run --with-requirements backend/requirements.txt pytest tests/backend -v
```

### Test Frontend (Vitest)
```bash
# Esecuzione completa di tutti i 25 test dei componenti Vue 3
npm --prefix frontend run test
```

### Build di Produzione Frontend
```bash
npm --prefix frontend run build
```

---

## 🔑 Mappa Porte e Riferimenti di Rete

| Servizio | Porta Host | Protocollo / Endpoint | Descrizione |
| :--- | :--- | :--- | :--- |
| **Frontend UI** | `5173` | `http://localhost:5173/` | Interfaccia Quasar Vue 3 (Vite HMR) |
| **Backend API** | `5000` | `http://localhost:5000/api/` | FastAPI Uvicorn REST & WebSockets (/ws) |
| **PostgreSQL** | `5432` | `postgresql://gabbo:gabbino@localhost:5432/erp9lli_dev` | RDBMS Relazionale |
| **Redis** | `6379` | `redis://localhost:6379/0` | Event Bus & Code RQ |

---

## 📄 Licenza e Note di Proprietà
Sviluppato per la gestione integrata delle reti biologiche e della filiera agroalimentare. Rilasciato sotto licenza MIT.
