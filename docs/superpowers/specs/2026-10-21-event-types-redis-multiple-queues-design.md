# Specifica Architetturale: Catalogo EventType, Code Multiple con Redis Queue (RQ) e Policy Sincrono/Asincrono

## 1. Obiettivo e Panoramica Funzionale

Implementare nel gestionale **`erp9lli`** l'architettura a **Code Multiple basata su Redis Queue (`rq`)** e il **Catalogo degli Eventi Registrabili (`EventType`)**:
- **Catalogo Dichiarativo degli Eventi (`EventType`)**:
  - Ogni operazione di business (es. `EMISSIONE_DDT`, `CARICO_MERCI`, `SOLLECITO_PALLET`, `SOLLECITO_MASSIVO_PALLET`) viene censita in una tabella anagrafica dedicata.
  - Per ciascun evento è configurabile la **Modalità di Esecuzione**:
    - **`sincrono`**: esecuzione immediata all'interno della richiesta HTTP (es. emissione di un DDT, carico di un lotto);
    - **`asincrono`**: presa in carico in background con risposta immediata `HTTP 202 Accepted` e monitoraggio del progresso (es. invio solleciti email, elaborazioni batch).
- **Architettura a Code Multiple con Redis Queue (RQ)**:
  - Sfrutta il container `redis:alpine` già presente in `docker-compose.yaml` (porta 6379).
  - Partizionamento del carico su **4 code nominate dedicate** per evitare l'intasamento della coda (Head-of-Line Blocking):
    1. **`critical`**: avvisi urgenti, blocchi operativi o webhook verso sistemi esterni;
    2. **`emails`**: invio di solleciti pallet e fatture di cortesia (con rate-limiting per evitare blocchi SMTP);
    3. **`batch`**: elaborazioni pesanti e massive (es. invio solleciti massivi a 50 debitori, chiusure fine mese);
    4. **`default`**: task generici asincroni in background.
  - Ogni tipo di evento indica la propria coda predefinita (`coda_nome`), modificabile dall'amministratore da interfaccia senza toccare codice.
- **Tracciamento e Collegamento su `SystemEvent`**:
  - La tabella degli eventi memorizza il riferimento all'evento registrato (`event_type_id`), il nome della coda su cui è stato instradato (`coda_nome`) e l'identificativo univoco del job Redis (`rq_job_id`).
- **Console di Controllo Quasar (`ActivityCenter.vue`)**:
  - Cruscotto di monitoraggio delle code Redis con conteggio dei job per ciascuna coda;
  - Scheda di configurazione delle policy per passare un evento da sincrono ad asincrono con un semplice click.

---

## 2. Modello Dati Relazionale (`backend/models/`)

### 2.1 Tabella `event_type` (`backend/models/event_type.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `codice` | String(50) | Not Null, Unique, Index | Codice evento (es. `EMISSIONE_DDT`, `SOLLECITO_PALLET`) |
| `nome` | String(100) | Not Null | Nome descrittivo per l'utente |
| `descrizione` | Text | Nullable | Descrizione funzionale |
| `channel_id` | Integer | FK `event_channel.id`, Not Null | Canale di default (`AUDIT`, `EMAIL`, `PEC`, `WEBHOOK`) |
| `category_id` | Integer | FK `event_category.id`, Nullable | Area applicativa (`LOGISTICA`, `PALLET`, `FISCALE`) |
| `modalita_esecuzione`| String(20) | Not Null, default `'sincrono'` | `'sincrono'` oppure `'asincrono'` |
| `coda_nome` | String(30) | Not Null, default `'default'` | Coda Redis: `'critical'`, `'emails'`, `'batch'`, `'default'` |
| `livello_default` | String(20) | Not Null, default `'info'` | `'info'`, `'success'`, `'warning'`, `'error'` |
| `attivo` | Boolean | Not Null, default `True` | Evento abilitato |

### 2.2 Estensione di `system_event` (`backend/models/system_event.py`)
| Campo Aggiunto | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `event_type_id` | Integer | FK `event_type.id`, Nullable | Tipo di evento registrato |
| `coda_nome` | String(30) | Nullable | Nome della coda Redis utilizzata |
| `rq_job_id` | String(50) | Nullable | ID del job generato da Redis Queue |

---

## 3. Specifiche Architetturali del Dispatcher (`backend/services/event_dispatcher.py`)

### 3.1 Funzione `dispatch_event` con Lookup su `EventType`
```python
def dispatch_event(
    event_type_code=None,       # Codice da catalogo (es. "SOLLECITO_PALLET")
    channel_code=None,          # Se None, ereditato da event_type.channel
    category_code=None,         # Se None, ereditato da event_type.category
    azione=None,
    titolo=None,
    descrizione=None,
    payload_dati=None,
    destinatario_recapito=None,
    partner_id=None,
    entita_tipo=None,
    entita_id=None,
    utente=None,
    is_async=None,              # Se None, ereditato da event_type.modalita_esecuzione == 'asincrono'
    coda_nome=None,             # Se None, ereditato da event_type.coda_nome
    target_func=None
) -> SystemEvent:
```

### 3.2 Regole di Routing:
1. Il dispatcher recupera la configurazione da `EventType`:
   - Se `modalita_esecuzione == 'asincrono'` (o `is_async=True` esplicito):
     - Seleziona la coda Redis corretta (`Queue(coda_nome, connection=redis_conn)`);
     - Accoda il job e salva `rq_job_id = job.id` e `coda_nome = coda`;
     - In ambiente di test / fallback: esecuzione controllata nel thread worker locale per isolamento;
     - Restituisce immediatamente **`202 Accepted`**;
   - Se `modalita_esecuzione == 'sincrono'`:
     - Esegue l'evento istantaneamente con `progresso = 100`, `stato = 'completato'` (o `'test'`) e restituisce **`201 Created`**.

---

## 4. Specifiche API REST (`backend/app.py`)

Tutti gli endpoint richiedono `@require_auth()`:

- **`GET /api/events/types`**:
  - Elenco di tutti gli eventi censiti con policy sincrono/asincrono e coda associata.
- **`POST /api/events/types`**:
  - Censimento di un nuovo tipo di evento con assegnazione canale, categoria e coda.
- **`PUT /api/events/types/<int:id>`**:
  - Modifica della policy in tempo reale:
    ```json
    {
      "modalita_esecuzione": "asincrono",
      "coda_nome": "emails"
    }
    ```
- **`GET /api/events/queues`**:
  - Statistiche in tempo reale delle 4 code Redis (`critical`, `emails`, `batch`, `default`):
    ```json
    {
      "queues": [
        {"name": "critical", "count": 0},
        {"name": "emails", "count": 2},
        {"name": "batch", "count": 1},
        {"name": "default", "count": 0}
      ]
    }
    ```

---

## 5. Specifiche Interfaccia Quasar (`ActivityCenter.vue`)

- **Nuova Scheda "Catalogo Eventi & Code Redis"**:
  - Tabella degli eventi registrabili con:
    - Chip e selettore rapido **Modalità** (*Sincrono* vs *Asincrono*);
    - Selettore a tendina per la **Coda Redis** (`critical`, `emails`, `batch`, `default`);
    - Canale di default collegato (`AUDIT`, `EMAIL`, ecc.);
  - Riquadro contatori delle code Redis attive in cima alla scheda con badge e pulsante di aggiornamento;
  - Possibilità di salvare le modifiche alle policy con feedback immediato Quasar Notify.

---

## 6. Strategia di Test Automatizzati

### 6.1 Test Backend (`tests/backend/test_event_types_queues.py` - Pytest)
1. `test_event_type_model_persistence_and_defaults`: verifica persistenza modello `EventType` e campi `modalita_esecuzione` e `coda_nome`.
2. `test_system_event_extended_fields`: verifica presenza `event_type_id`, `coda_nome` e `rq_job_id`.
3. `test_dispatch_event_declarative_async_from_event_type`: verifica che un evento con `modalita_esecuzione='asincrono'` venga automaticamente eseguito in background e instradato sulla coda corretta.
4. `test_api_event_types_crud_and_policy_update`: verifica modifica via PUT della modalità da sincrono ad asincrono.
5. `test_api_redis_queues_stats`: verifica endpoint statistiche code Redis.

### 6.2 Test Frontend (`tests/frontend/ActivityCenter.spec.js` - Vitest)
1. Verifica visualizzazione scheda catalogo eventi registrabili e widget code Redis.
