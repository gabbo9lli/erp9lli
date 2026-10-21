# Specifica Architetturale: Modulo Spedizioni Internazionali e Lettere di Vettura CMR (Export)

## 1. Obiettivo e Panoramica Funzionale

Implementare nel gestionale **`erp9lli`** il modulo **`cmr`** per la gestione delle **Spedizioni Internazionali ed Export**, conforme ai requisiti della **Convenzione di Ginevra del 1956 sul Contratto di Trasporto Internazionale di Merci su Strada (CMR)** e alle automazioni di **Gestionale ReteBio 2026** (sezione 5.5):
- **Generazione Automatica da DDT di Vendita Estero**:
  - Attivazione istantanea per tutte le spedizioni verso clienti la cui nazione sia diversa dall'Italia (`nazione != 'IT'`, es. Belgio, Germania, Francia, Svizzera).
  - Numerazione progressiva annuale univoca del documento di trasporto internazionale (`CMR-YYYY-XXXX`).
- **Precompilazione Intelligente del Vettore e Luogo di Carico**:
  - Se il vettore designato sul DDT è *"LD TRASPORTI"* (il partner logistico internazionale primario di ReteBio), il sistema precompila automaticamente la casella 4 (Luogo e data di presa in carico) con:
    $$\text{Luogo di carico} = \text{"ALESSANDRIA (AL)"}$$
  - Per vettori terzi (es. Interfrigo), il campo rimane liberamente modificabile dall'operatore.
- **Regola Intelligente delle 21 Righe**:
  - **Fino a 21 righe merce**: tutti i dettagli vengono impaginati direttamente all'interno delle caselle standard 6-12 del CMR.
  - **Oltre 21 righe merce**: il sistema imposta automaticamente il flag `ha_allegato_righe = True`, inserisce nel corpo CMR la dicitura convenzionale:
    $$\text{"--- VEDI ELENCO MERCE IN ALLEGATO ---"}$$
    e genera la distinta separata delle merci con pesi e colli aggregati.
- **Raggruppamento Doganale per Codice NC**:
  - Aggregazione opzionale delle righe per codice doganale omogeneo (Nomenclatura Combinata), sommando colli e convertendo i pesi in Kg netti/lordi con indicazione dell'origine biologica preferenziale CE.
- **Totale Disaccoppiamento Modulare**:
  - Governato dal feature flag `cmr` in `AVAILABLE_MODULES`, disattivabile senza pregiudicare il ciclo attivo nazionale.

---

## 2. Modello Dati Relazionale (`backend/models/`)

### 2.1 Tabella `cmr_document` (`backend/models/cmr_document.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco documento CMR |
| `numero` | Integer | Not Null | Progressivo annuale (1, 2, 3...) |
| `anno` | Integer | Not Null | Anno solare di emissione (es. 2026) |
| `numero_completo` | String(30) | Not Null, Unique, Index | Formato stringa (`CMR-YYYY-XXXX`) |
| `data_documento` | Date | Not Null, default `today` | Data emissione lettera di vettura |
| `delivery_note_id` | Integer | FK `delivery_note.id`, Nullable | DDT di vendita d'origine |
| `cliente_id` | Integer | FK `partner.id`, Not Null | Destinatario estero (Casella 2) |
| `vettore_id` | Integer | FK `partner.id`, Nullable | Vettore incaricato (Casella 16) |
| `luogo_carico` | String(100) | Not Null, default `'ALESSANDRIA (AL)'` | Casella 4 (Presa in carico della merce) |
| `luogo_consegna` | String(200) | Not Null | Casella 3 (Luogo previsto per la consegna) |
| `targa_automezzo` | String(20) | Nullable | Targa trattore stradale |
| `targa_rimorchio` | String(20) | Nullable | Targa semirimorchio |
| `istruzioni_mittente` | Text | Nullable | Casella 13 (Istruzioni del mittente / dogana) |
| `totale_colli` | Integer | Not Null, default `0` | Casella 8 (Numero dei colli) |
| `peso_totale_netto` | Float | Not Null, default `0.0` | Totale Kg netti |
| `peso_totale_lordo` | Float | Not Null, default `0.0` | Casella 11 (Peso lordo in Kg) |
| `ha_allegato_righe` | Boolean | Not Null, default `False` | True se le righe superano la soglia 21 |
| `stato` | String(20) | Not Null, default `'emesso'` | `'bozza'`, `'emesso'` |

### 2.2 Tabella `cmr_item` (`backend/models/cmr_item.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco di riga |
| `cmr_document_id` | Integer | FK `cmr_document.id`, Not Null | Riferimento testata (cascade delete) |
| `riga_numero` | Integer | Not Null, default `1` | Numero progressivo riga |
| `contrassegno_lotto`| String(50) | Nullable | Casella 7 (Contrassegni e numeri / lotti bio) |
| `numero_colli` | Integer | Not Null, default `1` | Casella 8 (Numero dei colli) |
| `modo_imballaggio` | String(50) | Not Null, default `'Casse su Pallet'` | Casella 9 (Modo d'imballaggio) |
| `natura_merce` | String(200) | Not Null | Casella 10 (Denominazione della merce) |
| `codice_nc` | String(20) | Nullable | Nomenclatura combinata doganale |
| `peso_lordo_kg` | Float | Not Null, default `0.0` | Casella 11 (Peso lordo in Kg) |
| `peso_netto_kg` | Float | Not Null, default `0.0` | Peso netto in Kg |

---

## 3. Specifiche API REST (`backend/app.py`)

Tutti gli endpoint richiedono `@require_auth()`:

- **`GET /api/cmr`**:
  - Parametri filtro: `cliente_id`, `vettore_id`, `anno`, `search`.
  - Elenco lettere di vettura emesse con totali colli e pesi.
- **`GET /api/cmr/<id>`**:
  - Dettaglio completo con caselle 1-24 e righe merci raggruppate.
- **`POST /api/cmr/from-ddt/<int:ddt_id>`**:
  - Generazione automatica da DDT:
    - Recupera il DDT e controlla che il cliente sia estero (o consenta export).
    - Precompila `luogo_carico = "ALESSANDRIA (AL)"` se il vettore è *"LD TRASPORTI"*.
    - Clona le righe merce del DDT in `CmrItem`.
    - Se `len(items) > 21`, imposta `ha_allegato_righe = True`.
    - Calcola `totale_colli`, `peso_totale_netto` e `peso_totale_lordo`.
    - Genera progressivo annuale `CMR-YYYY-XXXX` e salva a DB.
    - Risposta `201 Created`.
- **`POST /api/cmr`**:
  - Emissione manuale diretta indipendente da DDT.
- **`PUT /api/cmr/<id>`**:
  - Aggiornamento targhe automezzo/rimorchio, luogo di carico/consegna e istruzioni del mittente.
- **`GET /api/cmr/<id>/print`**:
  - Restituisce la struttura dati standard a 24 caselle della Convenzione CMR per l'anteprima di stampa PDF.

---

## 4. Specifiche Interfaccia Utente Quasar (`frontend/src/`)

### 4.1 Integrazione Rapida in `DeliveryNotes.vue`
- Nella tabella DDT di vendita:
  - Se `props.row.cliente?.nazione !== 'IT'`, nella colonna azioni compare il pulsante blu **"CMR"** (`icon="flight_takeoff"` o `icon="public"`).
  - Cliccandolo, genera all'istante la lettera di vettura con un click e reindirizza alla visualizzazione CMR.

### 4.2 Componente `CmrManagement.vue`
- Tabella delle lettere di vettura emesse con bandierina/codice nazione destinatario (`BE`, `DE`, `FR`), numero documento, vettore, targhe, colli e pesi.
- **Visualizzatore Modello CMR a Caselle**:
  - Schermata responsive che riproduce graficamente il classico modello internazionale a 24 riquadri:
    - *Casella 1*: Mittente (ReteBio)
    - *Casella 2*: Destinatario estero
    - *Casella 3*: Luogo di consegna previsto
    - *Casella 4*: Luogo e data di carico (Alessandria)
    - *Casella 6-12*: Marchi, Colli, Natura Merci, Pesi (oppure alert allegato se > 21 righe)
    - *Casella 13*: Istruzioni mittente e diciture doganali
    - *Casella 16*: Vettore trasportatore e targhe
- Dialog di modifica rapida dati trasporto (targa camion, targa rimorchio, luogo carico).

### 4.3 Sidebar e Navigazione Dinamica (`App.vue` & `router.js`)
- Registrazione modulo `"cmr"` in `AVAILABLE_MODULES`.
- Voce **"Lettere di Vettura (CMR)"** sotto il gruppo *Logistica & Magazzino*, protetta da `v-if="activeModules.cmr"`.
- Nuova rotta protetta `/cmr` in `router.js`.

---

## 5. Strategia di Test Automatizzati

### 5.1 Test Backend (`tests/backend/test_cmr_export.py` - Pytest)
1. `test_cmr_models_persistence`: verifica modello e relazioni.
2. `test_create_cmr_from_ddt_with_alessandria_hub`: verifica generazione automatica da DDT con cliente estero e precompilazione luogo carico *"ALESSANDRIA (AL)"* per vettore *"LD TRASPORTI"*.
3. `test_cmr_21_rows_rule_and_attachment_flag`:
   - Con 10 righe: `ha_allegato_righe = False`.
   - Con 25 righe: `ha_allegato_righe = True`.
4. `test_cmr_print_format_boxes`: verifica che la risposta di stampa contenga tutte le 24 caselle della convenzione internazionale.

### 5.2 Test Frontend (`tests/frontend/CmrManagement.spec.js` - Vitest)
1. Verifica rendering tabella CMR, bandierina nazione estera e visualizzatore caselle documento.

---

## 6. Piano di Migrazione Database
- Esecuzione migrazione Alembic nel container Docker:
  `flask db migrate -m "add cmr international shipping models"`
  `flask db upgrade`
