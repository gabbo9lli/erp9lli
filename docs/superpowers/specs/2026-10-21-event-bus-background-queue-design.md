# Specifica Architetturale: Event Bus, Audit Trail, Canali Estendibili e Coda Task in Background

## 1. Obiettivo e Panoramica Funzionale

Implementare nel gestionale **`erp9lli`** una dorsale architetturale unificata per:
1. **Audit Trail & Logging Attività Utente**: tracciamento sistematico e persistente di tutte le operazioni di business (chi ha creato o confermato un DDT, chi ha evaso un ordine, chi ha incassato una rata o movimentato un lotto);
2. **Canali di Comunicazione Estendibili (`EventChannel`)**: anagrafica configurabile che definisce i canali di ricezione/invio (`AUDIT`, `EMAIL`, `PEC`, `WEBHOOK`, ecc.), i relativi tipi di dispatcher (`internal`, `smtp`, `webhook`) e le configurazioni custom;
3. **Dispatcher Polimorfico con Gestione Ambienti (Test vs Prod)**:
   - Se in ambiente **Dev/Test** (`SMTP_ENABLED != 'true'` o `FLASK_ENV == 'development'`): il dispatcher non effettua chiamate esterne o spedizioni accidentali, ma archivia il messaggio a DB con stato **`test`**;
   - Se in ambiente **Produzione**: esegue la trasmissione reale (via SMTP o HTTP) aggiornando lo stato a **`completato`** (o **`errore`** in caso di fault);
4. **Coda di Background per Task a Lunga Durata (Job Queue)**:
   - Gestione asincrona non bloccante per operazioni lente o massive (es. invio solleciti pallet massivi a 30 debitori, elaborazioni batch di fine mese);
   - Risposta HTTP istantanea **`202 Accepted`** con restituzione del `task_id`;
   - Esecuzione in thread worker in background con monitoraggio del `progresso` percentuale (0-100%) in tempo reale tramite Socket.IO o polling;
5. **Console Operativa Unificata Quasar (`ActivityCenter.vue`)**:
   - Visualizzatore timeline audit, cruscotto coda di background con barre di avanzamento, registro comunicazioni outbox e configuratore anagrafica canali.

---

## 2. Modello Dati Relazionale (`backend/models/`)

### 2.1 Tabella `event_channel` (`backend/models/event_channel.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `codice` | String(30) | Not Null, Unique, Index | Codice canale (es. `AUDIT`, `EMAIL`, `PEC`, `WEBHOOK`) |
| `nome` | String(100) | Not Null | Nome descrittivo (es. "Audit Log Attività", "Email Ordinaria") |
| `descrizione` | Text | Nullable | Descrizione funzionale |
| `tipo_dispatcher` | String(30) | Not Null, default `'internal'` | `'internal'`, `'smtp'`, `'webhook'` |
| `configurazione` | JSON | Nullable | Parametri opzionali (porte, template, endpoint) |
| `richiede_destinatario` | Boolean | Not Null, default `False` | True se richiede indirizzo o recapito |
| `attivo` | Boolean | Not Null, default `True` | Canale abilitato |

### 2.2 Tabella `event_category` (`backend/models/event_category.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `codice` | String(30) | Not Null, Unique, Index | Codice area (es. `LOGISTICA`, `VENDITE`, `ACQUISTI`, `FISCALE`, `PALLET`, `SISTEMA`) |
| `nome` | String(100) | Not Null | Nome visualizzato (es. "Logistica & Magazzino") |
| `colore_badge` | String(20) | Not Null, default `'primary'` | Colore Quasar (`teal`, `indigo`, `deep-orange`, ecc.) |
| `icona` | String(30) | Not Null, default `'info'` | Icona Material Design |
| `attivo` | Boolean | Not Null, default `True` | Categoria attiva |

### 2.3 Tabella `system_event` (`backend/models/system_event.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco evento/task |
| `channel_id` | Integer | FK `event_channel.id`, Not Null | Canale associato |
| `category_id` | Integer | FK `event_category.id`, Nullable | Categoria/Area |
| `livello` | String(20) | Not Null, default `'info'` | `'info'`, `'success'`, `'warning'`, `'error'` |
| `azione` | String(50) | Not Null | Tipo operazione (es. `emissione_ddt`, `sollecito_pallet`) |
| `titolo` | String(200) | Not Null | Titolo sintetico o oggetto comunicazione |
| `descrizione` | Text | Nullable | Dettaglio attività o corpo email |
| `payload_dati` | JSON | Nullable | Dati di input o parametri del task |
| `risultato_dati` | JSON | Nullable | Esito o risultati generati |
| `utente_id` | Integer | FK `user.id`, Nullable | ID operatore che ha eseguito o lanciato il task |
| `utente_email` | String(120) | Nullable | Email dell'operatore |
| `partner_id` | Integer | FK `partner.id`, Nullable | Cliente, fornitore o vettore associato |
| `destinatario_recapito`| String(200) | Nullable | Email/PEC o endpoint di destinazione |
| `entita_tipo` | String(30) | Nullable | `'delivery_note'`, `'invoice'`, `'pallet_receipt'`, `'order'` |
| `entita_id` | Integer | Nullable | ID dell'entità collegata |
| `is_async` | Boolean | Not Null, default `False` | True se eseguito in background |
| `progresso` | Integer | Not Null, default `0` | Avanzamento da 0 a 100% |
| `stato` | String(20) | Not Null, default `'in_coda'` | `'in_coda'`, `'in_corso'`, `'completato'`, `'test'`, `'errore'` |
| `tentativi` | Integer | Not Null, default `0` | Conteggio tentativi eseguiti |
| `max_tentativi` | Integer | Not Null, default `3` | Limite massimo ritentativi |
| `data_creazione` | DateTime | Not Null, default `now` | Timestamp creazione |
| `data_inizio_esecuzione`| DateTime | Nullable | Inizio presa in carico worker |
| `data_completamento` | DateTime | Nullable | Fine esecuzione |
| `note_esito` | Text | Nullable | Note di chiusura o traccia eccezione |

---

## 3. Specifiche Architetturali del Dispatcher (`backend/services/event_dispatcher.py`)

### 3.1 Funzione `dispatch_event`
```python
def dispatch_event(
    channel_code="AUDIT",
    category_code="SISTEMA",
    azione="azione_generica",
    titolo="Titolo",
    descrizione=None,
    payload_dati=None,
    destinatario_recapito=None,
    partner_id=None,
    entita_tipo=None,
    entita_id=None,
    utente=None,
    is_async=False,
    livello="info"
) -> SystemEvent:
```

### 3.2 Regole di Esecuzione Polimorfica:
1. **Canale `AUDIT` (`tipo_dispatcher == 'internal'`)**:
   - Esecuzione sincrona immediata;
   - `stato = 'completato'`, `progresso = 100`, `data_completamento = now()`.
2. **Canale `EMAIL` / `PEC` (`tipo_dispatcher == 'smtp'`)**:
   - Verifica variabile ambiente `SMTP_ENABLED`:
     - Se `False` (o in sviluppo/test):
       - Salva su DB impostando **`stato = 'test'`**;
       - `note_esito = "Evento archiviato in modalità test. Nessuna spedizione esterna eseguita."`;
     - Se `True` (produzione con host configurato):
       - Esegue la trasmissione via server SMTP;
       - Se successo: `stato = 'completato'`, `data_completamento = now()`;
       - Se eccezione: `stato = 'errore'`, `note_esito = str(err)`.
3. **Modalità Asincrona (`is_async == True`)**:
   - Salva record con `stato = 'in_coda'`, `progresso = 0`;
   - Accoda il task al `ThreadPoolExecutor` di background;
   - Il thread worker aggiorna lo stato a `'in_corso'`, esegue il job aggiornando il campo `progresso` (es. `25% -> 50% -> 100%`) ed emette l'evento Socket.IO `event_progress`;
   - A conclusione: imposta `stato = 'test'` (in ambiente dev) oppure `'completato'`.

---

## 4. Specifiche API REST (`backend/app.py`)

Tutti gli endpoint richiedono `@require_auth()`:

- **`GET /api/events/channels` & `POST /api/events/channels`**:
  - Anagrafica e censimento canali estendibili (con seed di `AUDIT`, `EMAIL`, `PEC`, `WEBHOOK`).
- **`GET /api/events/categories`**:
  - Elenco categorie strutturate con icone e colori.
- **`GET /api/events`**:
  - Elenco eventi/task con filtri per `channel_id`, `category_id`, `stato`, `is_async`, `search`.
- **`GET /api/events/<int:id>`**:
  - Dettaglio completo con payload, risultato e log di progresso.
- **`POST /api/events`**:
  - Creazione evento sincrono o lancio task in background.
- **`POST /api/events/<int:id>/retry`**:
  - Riavvio di un task fallito o ritentativo di invio.
- **`POST /api/pallets/batch-solleciti`**:
  - Procedura di business asincrona: individua tutti i buoni pallet scaduti ed esegue l'invio massivo in background sul canale `EMAIL`, restituendo `202 Accepted` con monitoraggio del progresso.

---

## 5. Specifiche Interfaccia Quasar (`ActivityCenter.vue`)

Console a 4 schede accessibile da `/activities` (sidebar sotto Amministrazione):
1. **Registro Attività (Audit Trail)**:
   - Timeline grafica delle azioni svolte con avatar utente, chip colorati per categoria e link all'entità collegata.
2. **Coda Task in Background (Jobs)**:
   - Tabella dei processi a lunga durata con progress bar attiva `q-linear-progress`, animazione per lo stato `in_corso` e pulsante di retry per `errore`.
3. **Comunicazioni in Uscita (Outbox)**:
   - Elenco email e messaggi con chip distintivo verde (*Completato*) vs azzurro (*Test*), visualizzatore testo e destinatario.
4. **Anagrafica Canali**:
   - Tabella di gestione dei canali con configurazioni e stato di abilitazione.

Integrazione in **`Pallets.vue`**:
- Pulsante *"Sollecito"* per singolo buono con dialog di anteprima testo;
- Pulsante *"Invia Solleciti Massivi a Scaduti"* che invoca la coda di background e mostra l'avanzamento.

---

## 6. Strategia di Test Automatizzati

### 6.1 Test Backend (`tests/backend/test_event_bus.py` - Pytest)
1. `test_event_channel_and_category_models`: persistenza anagrafiche e seed di default.
2. `test_dispatch_audit_event_synchronous`: verifica scrittura istantanea con stato `completato`.
3. `test_dispatch_email_in_test_environment`: verifica che in ambiente test lo stato risulti `'test'` senza chiamate esterne.
4. `test_background_async_task_progress`: verifica esecuzione in background, incremento progresso 0 -> 100% e stato finale.
5. `test_pallet_batch_solleciti_background`: verifica avvio batch solleciti massivi con risposta 202.

### 6.2 Test Frontend (`tests/frontend/ActivityCenter.spec.js` - Vitest)
1. Verifica rendering delle schede Audit Trail, Coda Task, Comunicazioni e canali.
