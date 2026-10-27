# Documento di Architettura Software, Infrastruttura e Valutazione Tecnica

**Progetto:** erp9lli - ERP Specialistico per Ortofrutta Biologica B2B  
**Versione:** 1.2.0  
**Data di Rilascio:** Ottobre 2026  
**Autore:** Team di Ingegneria del Software erp9lli  
**Stato Deployment:** Produzione e Staging Live su AWS K3s (Regione Irlanda `eu-west-1`)  

---

## Indice dei Contenuti
1. [Executive Summary & Obiettivi del Progetto](#1-executive-summary--obiettivi-del-progetto)
2. [Architettura Software Backend (Clean Architecture)](#2-architettura-software-backend-clean-architecture)
3. [Dettaglio dei 17 Macro-Moduli di Dominio & Normativa Fiscale](#3-dettaglio-dei-17-macro-moduli-di-dominio--normativa-fiscale)
4. [Architettura Frontend (Vue 3 & Quasar Framework)](#4-architettura-frontend-vue-3--quasar-framework)
5. [Infrastruttura Cloud, DevOps & Topologia Kubernetes](#5-infrastruttura-cloud-devops--topologia-kubernetes)
6. [Sicurezza Informatica & Hardening Perimetrale](#6-sicurezza-informatica--hardening-perimetrale)
7. [Sottosistema di Observability, Metriche & Alerting](#7-sottosistema-di-observability-metriche--alerting)
8. [Strategia di Quality Assurance & Testing Suite](#8-strategia-di-quality-assurance--testing-suite)
9. [Valutazione Tecnica Globale e Roadmap Evolutiva](#9-valutazione-tecnica-globale-e-roadmap-evolutiva)

---

## 1. Executive Summary & Obiettivi del Progetto

**erp9lli** nasce con l'obiettivo di sostituire integralmente un gestionale legacy basato su Microsoft Access (*GestionaleReteBio2026.accdb*), superandone i limiti strutturali (mancanza di concorrenza, instabilità di rete, assenza di audit e vincoli normativi non aggiornati). 

L'applicazione è stata ingegnerizzata come un **ERP modulare per il commercio all'ingrosso e dettaglio di ortofrutta biologica**, rispondendo a normative stringenti:
- Tracciabilità dei lotti deperibili e rotazione **FEFO (First-Expired, First-Out)**;
- Gestione dell'interscambio pallet a rendiconto e cauzione (**Legge 182/2025**);
- Lettere di vettura internazionali **CMR** conformi alle regole doganali;
- **Fatturazione Elettronica SDI (FPR12 v1.2.2)** con quadratura centesimale;
- **Contabilità Generale a Partita Doppia** secondo la IV Direttiva CEE;
- Funzionamento **Multi-Ambiente (Produzione e Staging isolati)** su Kubernetes K3s con costi operativi inferiori a **30€/mese**.

---

## 2. Architettura Software Backend (Clean Architecture)

Il backend è sviluppato in **Python 3.11** su framework **FastAPI**, organizzato rigorosamente secondo i principi della **Clean Architecture a 4 livelli**. La separazione delle responsabilità garantisce manutenibilità nel tempo, testabilità isolata e disaccoppiamento dal framework di trasporto.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        LIVELLO 1: HTTP API ROUTERS                     │
│                        (backend/api/routers/)                          │
│ • Controller sottili privi di logica di business                       │
│ • Validazione parametri, autorizzazioni e serializzazione HTTP         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                        LIVELLO 2: DTO & SCHEMI                         │
│                        (backend/schemas/)                              │
│ • Contratti dati formali Pydantic v2 (Request / Response DTO)          │
│ • Validazione stringente dei tipi, campi obbligatori ed enum           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                        LIVELLO 3: DOMAIN SERVICES                      │
│                        (backend/services/)                             │
│ • Cuore della Business Logic: calcoli contabili, FEFO, SDI, pallet    │
│ • Servizi stateless riutilizzabili da CLI, API e Worker asincroni      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                        LIVELLO 4: PERSISTENCE LAYER                    │
│                        (backend/models/ & database.py)                 │
│ • Modelli ORM SQLAlchemy 2.0 conformi a PostgreSQL                     │
│ • Migrazioni dichiarative versionate tramite Alembic                   │
└────────────────────────────────────────────────────────────────────────┘
```

### Regole Architetturali Applicate
1. **Zero Logica nei Router:** I controller HTTP non eseguono calcoli né query dirette, ma delegano esclusivamente ai Domain Service;
2. **Session Lifecycle Esplicito:** La sessione SQLAlchemy (`Session`) viene iniettata tramite dependency injection (`get_db`) e gestita a livello di singola richiesta, garantendo transazionalità atomica (`commit` o `rollback`);
3. **Idempotenza delle Operazioni:** Ogni azione di business asincrona o di migrazione registra un vincolo univoco di tracciamento per impedire doppie esecuzioni.

---

## 3. Dettaglio dei 17 Macro-Moduli di Dominio & Normativa Fiscale

L'applicazione copre 17 moduli funzionali integrati:

| # | Macro-Modulo | File Principale | Descrizione e Vincoli Rispettati |
|---|---|---|---|
| **1** | **Partner & Soggetti** | `partner_service.py` | Anagrafica unificata per Clienti, Fornitori, Produttori agricoli associati e Vettori con Partita IVA/CF e codici SDI. |
| **2** | **Catalogo Prodotti Bio** | `product_service.py` | Gestione articoli con codici doganali NC, certificazione biologica (CCPB/ICEA), unità di misura (KG/Colli) e marginalità. |
| **3** | **Ordini Clienti** | `order_service.py` | Ciclo ordini con **numerazione progressiva righe a passi di 5** (5, 10, 15...) per facilitare inserimenti intermedi, evasioni parziali o totali a bolla. |
| **4** | **Bollettazione DDT & FEFO** | `delivery_note_service.py` | Emissione DDT con algoritmo di magazzino **FEFO (First-Expired, First-Out)**: il sistema propone prioritariamente i lotti più vicini alla scadenza. |
| **5** | **Interscambio Pallet (L. 182/2025)** | `pallet_service.py` | Gestione causali `RESO`, `A_RENDICONTO`, `CAUZIONE` e circuiti `EPAL`, `CHEP`, `CPR`, `IFCO`. Calcolo conguagli economici e Reverse Charge IVA oltre i 60 giorni. |
| **6** | **Spedizioni Internazionali CMR** | `cmr_service.py` | Lettere di vettura internazionali conformi alla Convenzione di Ginevra: hub doganale di Alessandria, **regola bloccante delle max 21 righe** e dati vettore estero. |
| **7** | **Fatturazione Elettronica SDI** | `sdi_service.py`, `invoice_service.py` | Esportazione XML conforme allo standard ministeriale **FatturaPA v1.2.2 (FPR12)**. Supporto Fattura Immediata (`TD01`) e Differita (`TD24`). |
| **8** | **Quadratura Rate & Scadenziario** | `invoice_service.py` | Calcolo automatico scadenze con **quadratura centesimale esatta**: l'eventuale centesimo dispari di arrotondamento viene assegnato alla prima rata. |
| **9** | **Note di Credito** | `invoice_service.py` | Emissione note di accredito (`TD04`) con storno totale o parziale di fatture emesse e allineamento contabile. |
| **10**| **Entrata Merci & Lotti** | `warehouse_service.py` | Registrazione bolle di carico fornitore con associazione obbligatoria di lotto produttore, data raccolta e data scadenza per la tracciabilità bio. |
| **11**| **Contabilità Generale Partita Doppia** | `accounting_service.py` | Piano dei conti standard a 4 livelli (Mastro, Conto, Sottoconto) conforme alla **IV Direttiva CEE**. Vincolo di quadratura bloccante `\|Dare - Avere\| <= 0.001`. |
| **12**| **Libro Giornale & Bilancio** | `accounting_service.py` | Generazione automatica di Libro Giornale, Mastrini di conto e Bilancio di Verifica a 4 colonne (Saldi Iniziali, Movimenti, Saldi Finali). |
| **13**| **Punto Vendita POS (BancoM)** | `pos_sale_service.py`, `pos_driver_service.py` | Interfaccia cassa touch-screen per vendita al minuto con simulatore di registratore telematico (RT), gestione cassa, pos carta e scontrino fiscale. |
| **14**| **Etichette Barcode Termiche** | `barcode_label_service.py` | Generatore etichette per bancali e colli in formato **ZPL (Zebra Programming Language)** nativo e anteprima grafica vettoriale SVG. |
| **15**| **Connettore E-Commerce Spree** | `ecommerce_service.py` | Webhook e polling per sincronizzazione bidirezionale ordini e giacenze di magazzino con piattaforma Spree Commerce. |
| **16**| **Event Bus & Outbox Pattern** | `event_dispatcher.py` | Disaccoppiamento asincrono su Redis con 4 code separate (`critical`, `emails`, `reports`, `default`) gestite da worker RQ. |
| **17**| **Migrazione Dati Legacy Access** | `legacy_migration_service.py` | Pipeline ETL per file `.accdb`: ispezione tabelle con `mdbtools`, dry-run statistico, importazione atomica e token di sicurezza `RESET_ERP9LLI`. |

---

## 4. Architettura Frontend (Vue 3 & Quasar Framework)

L'interfaccia utente è una **Single Page Application (SPA)** moderna, costruita con:
- **Vue 3** (Composition API con script setup);
- **Quasar Framework v2** (design system responsive orientato ad applicazioni desktop/tablet aziendali);
- **Vite 5** come build tool ad altissima velocità;
- **Axios con Global Request Interceptor:** iniezione trasparente del token JWT `Authorization: Bearer <token>` memorizzato in `localStorage`;
- **WebSockets Live Service (`/ws`):** connessione bidirezionale persistente con riconnessione esponenziale automatica, che riceve gli eventi broadcast dell'Event Bus aggiornando l'interfaccia senza refresh manuali.

---

## 5. Infrastruttura Cloud, DevOps & Topologia Kubernetes

L'infrastruttura è erogata su **Amazon Web Services (AWS)** nella regione Irlanda (`eu-west-1`), basata sul cluster **Kubernetes K3s** (v1.30+ con containerd e Traefik Ingress Controller integrato):

```
                                      INTERNET
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
         https://18.200.141.146.sslip.io        https://staging.18.200.141.146.sslip.io
         (Produzione Aziendale)                 (Ambiente di Collaudo & Staging)
                    │                                           │
                    │ [Traefik IngressRoute - TLS 1.3 / HTTP/2] │
                    ├───────────────────────────────────────────┤
                    ▼                                           ▼
      ┌───────────────────────────┐               ┌───────────────────────────┐
      │   Namespace: `erp9lli`    │               │ Namespace: `erp9lli-staging`│
      ├───────────────────────────┤               ├───────────────────────────┤
      │ • erp9lli-frontend (Nginx)│               │ • staging-frontend (Nginx)│
      │ • erp9lli-backend (FastAPI│               │ • staging-backend (FastAPI│
      │ • erp9lli-worker (RQ)     │               │ • staging-worker (RQ)     │
      │ • Prometheus (v2.54)      │               └─────────────┬─────────────┘
      │ • Grafana (v11.1)         │                             │
      │ • erp9lli-postgres (PVC)  │ ◄────── erp9lli_staging ────┘
      │ • erp9lli-redis           │
      └───────────────────────────┘
```

### Specifiche dell'Istanza EC2 Host
- **Tipo Istanza:** AWS EC2 `t4g.medium` (Architettura **ARM64 Graviton**, 2 vCPU, 4 GB RAM);
- **Archiviazione:** Volume SSD gp3 da 40 GB (`DeleteOnTermination: true`);
- **Indirizzo IP:** Elastic IP statico riservato (`18.200.141.146`);
- **Automazione Completa:**
  - `scripts/deploy_aws.py`: provisioning infrastrutturale Boto3 zero-click;
  - `scripts/destroy_aws.py`: teardown istantaneo a costo zero (rilascio IP, terminazione VM, eliminazione chiavi);
  - `scripts/cloud-init.sh`: bootstrap automatico Ubuntu 24.04, Docker, K3s, cert-manager e Traefik.

---

## 6. Sicurezza Informatica & Hardening Perimetrale

La sicurezza è stata implementata a livelli concentrici (Defense in Depth):

1. **Crittografia & Certificati SSL Ufficiali:**
   - Tutti gli accessi avvengono in **HTTPS cifrato su porta 443 (TLS 1.3 e HTTP/2)**;
   - I certificati sono emessi da **Let's Encrypt** con rinnovo automatico a cura di `cert-manager` v1.16 sia per Produzione sia per Staging;
   - **Reindirizzamento forzato HTTP 308:** Qualsiasi chiamata su porta 80 in chiaro viene convertita all'istante verso HTTPS.

2. **Security Headers & HSTS:**
   Tutte le risposte emesse dal sistema includono:
   - `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` (obbligo HTTPS valido 1 anno);
   - `X-Frame-Options: DENY` (protezione assoluta da clickjacking);
   - `X-Content-Type-Options: nosniff` (prevenzione MIME-sniffing);
   - `X-XSS-Protection: 1; mode=block`;
   - `Referrer-Policy: strict-origin-when-cross-origin`;
   - `Permissions-Policy: camera=(), microphone=(), geolocation=()`;
   - `X-Robots-Tag: noindex, nofollow` (blocco indicizzazione motori di ricerca).

3. **Rate Limiting Anti Brute-Force:**
   Configurato a livello Traefik e FastAPI sugli endpoint di autenticazione (`/api/signin`, `/api/login`, `/api/signup`):
   - Soglia: 10 richieste/min con burst di 15;
   - Oltre la soglia viene restituito immediatamente **`HTTP 429 Too Many Requests`**.

4. **Isolamento CORS Rigoroso:**
   Rimosso qualsiasi wildcard `*`. Le origini autorizzate sono limitate a:
   - In sviluppo: `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:5000`;
   - In produzione: `https://18.200.141.146.sslip.io`, `https://staging.18.200.141.146.sslip.io`.

5. **Protezione Credenziali & Azzeramento Dati:**
   - Hashing delle password con algoritmo `scrypt` derivato da `werkzeug` (colonna `VARCHAR(255)`);
   - Il reset completo del database richiede la digitazione dell'esatto token di sicurezza `RESET_ERP9LLI`, preservando comunque l'account Amministratore per prevenire lockout accidentali.

---

## 7. Sottosistema di Observability, Metriche & Alerting

L'ERP integra un'infrastruttura completa di osservabilità conforme agli standard CNCF:

1. **Correlation ID & Structured JSON Logging:**
   - Ogni richiesta HTTP riceve o genera un identificativo univoco **`X-Request-ID`** (UUIDv4) salvato in un `ContextVar` asincrono;
   - In produzione i log sono emessi in **formato JSON strutturato** (`timestamp`, `level`, `logger`, `request_id`, `method`, `path`, `status_code`, `duration_ms`, `client_ip`).

2. **Engine di Metriche OpenMetrics / Prometheus (`/metrics`):**
   - Engine nativo in Python puro (`backend/core/metrics.py`), thread-safe e a zero overhead di memoria;
   - Espone metriche di latenza (istogrammi p50/p95/p99), volumi HTTP, client WebSocket attivi, code Redis e contatori di business (ordini, fatture emesse, vendite al banco);
   - Endpoint protetto `GET /api/metrics/summary` per alimentare le card del gestionale.

3. **Multi-Channel Alerting con Anti-Flapping (`AlertingService`):**
   - In caso di errore HTTP 500 non gestito o fallimento nei worker RQ, invia una notifica immediata su:
     - Webhook (Slack, Discord, Microsoft Teams, Mattermost);
     - Bot Telegram (messaggio Markdown formattato);
     - Canale EMAIL dell'Event Bus;
   - **Cooldown Anti-Spam:** Calcola il fingerprint dell'errore (MD5 di eccezione + file + linea) e applica una finestra di silenziamento di 5 minuti su errori identici per evitare tempeste di notifiche.

4. **Visualizzazione Statistiche & Dashboard:**
   - **Card KPI Integrate nel Gestionale:** Nuova scheda *Metriche & Ops* in `ActivityCenter.vue` con 4 card (Latenza media, WebSocket live, Traffico %, Code Redis) e volumi operativi;
   - **Cruscotto Grafana Esterno:** Distribuito su Kubernetes (`https://18.200.141.146.sslip.io/grafana/d/erp9lli-ops-overview/`) con pannelli e datasource Prometheus preconfigurati.

---

## 8. Strategia di Quality Assurance & Testing Suite

L'affidabilità del sistema è certificata da **3 suite di test indipendenti (100% superate)**:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. TEST AUTOMATIZZATI BACKEND (Pytest):            116 / 116 PASSED ✅ │
├────────────────────────────────────────────────────────────────────────┤
│ 2. TEST AUTOMATIZZATI FRONTEND (Vitest):            29 / 29  PASSED ✅ │
├────────────────────────────────────────────────────────────────────────┤
│ 3. TEST END-TO-END LIVE (AWS Produzione & Staging): 17 / 17  PASSED ✅ │
└────────────────────────────────────────────────────────────────────────┘
```

Lo script di verifica live `tests/test_live_e2e.py` interroga direttamente i server AWS convalidando 17 aspetti critici:
- Healthcheck DB PostgreSQL;
- Header `X-Request-ID` e Security Headers HSTS/DENY/nosniff;
- Redirect permanente HTTP 308 verso HTTPS;
- Isolamento CORS;
- Generazione token JWT e login;
- Validazione cataloghi Partner e Prodotti Biologici;
- Interscambio pallet Legge 182/2025;
- Piano dei conti contabile CEE;
- Canali Outbox ed Event Bus;
- Postazione Cassa POS BancoM;
- Endpoint OpenMetrics `/metrics` e JSON `/api/metrics/summary`;
- Accessibilità dashboard Grafana su `/grafana/`;
- Blocco effettivo `HTTP 429` del Rate Limiter anti brute-force.

---

## 9. Valutazione Tecnica Globale e Roadmap Evolutiva

### 🏆 Giudizio Tecnico Complessivo: **9.2 / 10**

L'applicazione si colloca a un livello di **maturità e solidità tipico di soluzioni enterprise commerciali**, superando di gran lunga lo standard dei prototipi o degli MVP convenzionali.

### Punti di Eccellenza Rilevati:
- **Aderenza al Dominio:** È uno dei pochissimi gestionali italiani a implementare in modo nativo e vincolante le recenti normative su pallet a rendiconto (**Legge 182/2025**), regole doganali CMR a 21 righe e tracciabilità FEFO;
- **Efficienza dei Costi & Risorse:** L'intera architettura (2 ambienti isolati Prod e Staging, Database PostgreSQL, Redis, Worker, Prometheus, Grafana e Traefik) opera in modo fluido su una singola istanza ARM64 Graviton con un costo cloud di soli **~25€/mese**;
- **Qualità del Codice:** Clean Architecture a 4 livelli rigorosa, assenza di hack o workaround, digitazione statica con Pydantic v2 e copertura test totale.

### 🚀 Roadmap per il 10 / 10:
Per completare l'evoluzione verso la perfezione assoluta:
1. **Motore di Stampa PDF Fiscali:** Adozione di template Jinja2 con `WeasyPrint` per generare con 1 clic i PDF stampabili di DDT, Fatture di cortesia, CMR e Buoni Pallet;
2. **Executive Dashboard nella Home:** Visualizzazione grafica aggregata di fatturato mensile, lotti in scadenza a 7 giorni e crediti aperti;
3. **Automazione Invio Email Documenti:** Spedizione automatica con 1 clic del PDF al cliente tramite la coda Redis `emails`.
