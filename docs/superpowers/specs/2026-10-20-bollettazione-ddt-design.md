# Specifica Architetturale: Modulo Bollettazione (DDT - Documenti di Trasporto) per erp9lli

## 1. Obiettivo e Panoramica Funzionale

Integrare nel gestionale **`erp9lli`** il modulo di **Bollettazione (DDT - Documenti di Trasporto)**, elemento cardine della logica di magazzino e spedizione derivato dall'esperienza di **Gestionale ReteBio 2026** (`T_AllaDataFA`, `RigheOrdArt`, `T_STAMPA_DDT`):
- **Numerazione Progressiva Annuale Automatica**: emissione automatica e protetta contro la concorrenza di numeri documento progressivi per anno solare (es. `DDT-2026-0001`, `DDT-2026-0002`).
- **Associazione Soggetti (`Partner`)**: indicazione del Cliente destinatario e del Vettore di trasporto (es. *LD Trasporti*, *Interfrigo*).
- **Tracciabilità Biologica Stringente**: per gli articoli contrassegnati con `in_scadenza = True` (ortofrutta fresca e trasformati deperibili), il sistema impone obbligatoriamente l'indicazione di **Codice Lotto** e **Data di Scadenza** sulla riga documento.
- **Calcolo Automatico Pesi e Colli**: aggregazione automatica in tempo reale del totale colli, peso netto (Kg), peso lordo (Kg) e totale imponibile (€).
- **Gestione Ciclo di Vita a Stati**:
  - `bozza`: documento aperto, liberamente modificabile dall'operatore.
  - `confermato`: documento validato e bloccato (immutabile), pronto per la consegna e per la futura **Fatturazione Differita**.
  - `fatturato`: documento associato a una fattura di vendita emessa.
- **Frontend Quasar Responsive**: gestione elenco DDT ed editor interattivo con griglia righe merci dinamica.

---

## 2. Modello Dati Relazionale (`backend/models.py`)

### 2.1 Tabella `delivery_note` (Testata Documento di Trasporto)
Rappresenta la testata della bolla di spedizione.

| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco di riga |
| `numero` | Integer | Not Null | Progressivo annuale (1, 2, 3...) |
| `anno` | Integer | Not Null | Anno solare di emissione (es. 2026) |
| `numero_completo` | String(30) | Not Null, Unique, Index | Formato stringa univoco (`DDT-YYYY-XXXX`) |
| `data_documento` | Date | Not Null | Data di emissione della bolla |
| `data_trasporto` | DateTime | Nullable | Data e ora inizio trasporto |
| `cliente_id` | Integer | FK `partner.id`, Not Null | Destinatario delle merci |
| `vettore_id` | Integer | FK `partner.id`, Nullable | Vettore incaricato del trasporto |
| `causale_trasporto`| String(50) | Not Null, default `'Vendita'`| `'Vendita'`, `'Conto Lavorazione'`, `'Reso'`, `'Omaggio'` |
| `porto` | String(20) | Not Null, default `'Franco'` | `'Franco'`, `'Assegnato'` |
| `aspetto_beni` | String(50) | Not Null, default `'Colli'` | `'Colli'`, `'Pallet'`, `'Casse CPR'`, `'A vista'` |
| `colli_totali` | Integer | Not Null, default `0` | Somma calcolata dei colli di riga |
| `peso_totale_netto`| Float | Not Null, default `0.0` | Somma calcolata pesi netti (Kg) |
| `peso_totale_lordo`| Float | Not Null, default `0.0` | Somma calcolata pesi lordi (Kg) |
| `totale_imponibile`| Float | Not Null, default `0.0` | Valore economico imponibile (€) |
| `stato` | String(20) | Not Null, default `'bozza'` | `'bozza'`, `'confermato'`, `'fatturato'` |
| `note` | Text | Nullable | Eventuali annotazioni per autista o cliente |

### 2.2 Tabella `delivery_note_item` (Righe Merci e Lotti)
Rappresenta le singole righe di prodotti trasportati.

| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco di riga |
| `delivery_note_id` | Integer | FK `delivery_note.id`, Not Null | Riferimento testata (cascade delete) |
| `product_id` | Integer | FK `product.id`, Not Null | Articolo trasportato |
| `descrizione` | String(200) | Not Null | Descrizione articolo (precompilata o custom) |
| `unita_misura` | String(10) | Not Null, default `'KG'` | UdM (`KG`, `PZ`, `LT`) |
| `colli` | Integer | Not Null, default `1` | Numero di colli/casse trasportate |
| `quantita` | Float | Not Null | Quantità totale (Kg netti o pezzi) |
| `prezzo_unitario` | Float | Not Null, default `0.0` | Prezzo di vendita concordato |
| `aliquota_iva` | Integer | Not Null, default `4` | Aliquota IVA applicabile (4, 10, 22) |
| `lotto` | String(50) | Nullable | **Obbligatorio** se `product.in_scadenza == True` |
| `data_scadenza` | Date | Nullable | **Obbligatoria** se `product.in_scadenza == True` |

---

## 3. Specifiche API REST (`backend/app.py`)

Tutti gli endpoint sono protetti tramite il decoratore di autenticazione `@require_auth()`:

- **`GET /api/delivery-notes`**:
  - Parametri di query: `stato` (`bozza`, `confermato`, `fatturato`), `cliente_id`, `anno`, `search` (cerca in numero, ragione sociale cliente).
  - Restituisce la lista dei DDT con totali e dati sintetici del cliente e vettore.
- **`GET /api/delivery-notes/<int:id>`**:
  - Restituisce il dettaglio completo della testata e l'array ordinato di `items` (righe merce con lotti e scadenze).
- **`POST /api/delivery-notes`**:
  - Creazione atomica di testata e righe.
  - Calcola `numero = MAX(numero) + 1` per l'anno del documento e genera `numero_completo = f"DDT-{anno}-{numero:04d}"`.
  - Verifica i vincoli di tracciabilità: se un articolo ha `in_scadenza == True`, solleva errore `400 Bad Request` qualora `lotto` o `data_scadenza` siano vuoti.
  - Calcola automaticamente i totali di colli, pesi e imponibile.
  - Risposta `201 Created`.
- **`PUT /api/delivery-notes/<int:id>`**:
  - Modifica di testata e/o righe.
  - **Vincolo**: consentito solo se `stato == 'bozza'`. Se il documento è già `confermato` o `fatturato`, restituisce `400 Bad Request` ("Cannot modify confirmed delivery note").
- **`DELETE /api/delivery-notes/<int:id>`**:
  - Eliminazione del DDT. Consentito solo se `stato == 'bozza'`.
- **`POST /api/delivery-notes/<int:id>/confirm`**:
  - Transizione di stato da `bozza` a `confermato`.
  - Verifica la presenza di almeno una riga merce e blocca il documento.

---

## 4. Specifiche Interfaccia Utente Quasar (`frontend/src/`)

### 4.1 Componente `DeliveryNotes.vue`
- Tabella `<q-table>` reattiva per consultare le bolle emesse:
  - Colonne: Numero (`DDT-2026-0001`), Data, Cliente, Vettore, Colli, Quantità (Kg), Imponibile (€), Stato (badge colorato: *Bozza* arancione, *Confermato* verde, *Fatturato* blu).
  - Barra filtri: tab rapidi per stato e campo di ricerca testuale.
  - Pulsante *"Nuovo DDT"*.

### 4.2 Componente `DeliveryNoteEditor.vue` (o modale esteso)
- **Dati di Testata**:
  - Selezione `Cliente` con ricerca interattiva.
  - Selezione `Vettore` (con precompilazione automatica).
  - Data documento, causale di trasporto (*Vendita*), aspetto dei beni e porto.
- **Griglia Righe Merce Dinamica**:
  - Selettore prodotto con autocompletamento (precompila descrizione, UdM, prezzo e aliquota IVA).
  - Campi: Colli, Quantità (Kg o Pz), Prezzo unitario.
  - Sezione Tracciabilità Bio: campi `Lotto` e `Scadenza` evidenziati e obbligatori se l'articolo è contrassegnato con icona *Bio / Lotti*.
  - Aggiunta/rimozione rapida di righe.
- **Riepilogo Totali Dinamico**:
  - Box di riepilogo in tempo reale: Totale Colli, Totale Quantità (Kg/Pz), Totale Imponibile (€).
- **Azioni**:
  - *"Salva Bozza"* (mantiene modificabile).
  - *"Conferma DDT"* (valida e blocca per fatturazione).

### 4.3 Navigazione Principale (`App.vue` & `router.js`)
- Nuova rotta protetta `/delivery-notes`.
- Aggiunta della voce **"Bolle (DDT)"** nella navbar principale di `App.vue`.

---

## 5. Strategia di Test Automatizzati

### 5.1 Test Backend (`tests/backend/test_delivery_notes.py` - Pytest)
1. `test_create_delivery_note_with_items_and_totals`: creazione testata e righe con calcolo corretto di colli e imponibile.
2. `test_auto_numbering_sequential`: verifica che la numerazione avanzi correttamente (`DDT-2026-0001`, `DDT-2026-0002`).
3. `test_bio_traceability_validation_failure`: inserimento articolo deperibile (`in_scadenza = True`) senza lotto/scadenza respinto con 400.
4. `test_bio_traceability_validation_success`: inserimento con lotto e scadenza accettato.
5. `test_confirm_delivery_note_transition`: transizione a stato `'confermato'`.
6. `test_modify_confirmed_delivery_note_rejected`: tentativo di modifica di un DDT confermato respinto con 400.

### 5.2 Test Frontend (`tests/frontend/DeliveryNotes.spec.js` - Vitest)
1. Verifica del corretto rendering della tabella DDT e visualizzazione chip di stato.
2. Verifica dell'interazione con l'editor righe e aggiornamento totali.

---

## 6. Piano di Migrazione Database
- Esecuzione migrazione Alembic nel container Docker:
  `flask db migrate -m "add delivery note models"`
  `flask db upgrade`
