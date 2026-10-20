# Specifica Architetturale: Modulo Fatturazione Attiva e Scadenzario Pagamenti per erp9lli

## 1. Obiettivo e Panoramica Funzionale

Completare il ciclo attivo di **`erp9lli`** implementando il modulo di **Fatturazione Attiva & Scadenzario Pagamenti**, derivato dalle procedure fiscali e contabili di **Gestionale ReteBio 2026** (`FATTURE`, `T1DettMovScad`, `CreaScadenze`):
- **Fatturazione Differita da DDT (TD24)**: selezione e raggruppamento dei DDT confermati per singolo cliente, clonazione delle righe merce (preservando lotti e scadenze bio) e aggiornamento contestuale dello stato dei DDT da `confermato` a `fatturato`.
- **Fatturazione Immediata (TD01)**: emissione contestuale alla vendita di fatture con righe merce dirette.
- **Castelletto IVA Automatico**: aggregazione e ripartizione automatica dell'imponibile e dell'imposta per ciascuna aliquota IVA applicata (4% fresco bio, 10% trasformati, 22% imballaggi/servizi) e gestione dello Split Payment (`esigibilita_iva = 'S'`).
- **Scadenzario Rate con Quadratura al Centesimo (`CreaScadenze`)**: calcolo automatico delle rate e delle date di scadenza in funzione delle condizioni commerciali concordate (`30gg fm`, `60gg fm`, `30/60gg fm`, `bonifico a vista`), con ripartizione e pareggio perfetto sul totale della fattura.
- **Console Gestione Scadenze**: monitoraggio globale dei crediti aperti, con alert visivo per le rate scadute e registrazione degli incassi con passaggio automatico della fattura a `saldata`.
- **Frontend Quasar**: visualizzazione fatture, wizard di generazione differita e gestione incassi rate.

---

## 2. Modello Dati Relazionale (`backend/models.py`)

### 2.1 Tabella `invoice` (Testata Fattura di Vendita)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `numero` | Integer | Not Null | Progressivo annuale (1, 2, 3...) |
| `anno` | Integer | Not Null | Anno solare di emissione (es. 2026) |
| `numero_completo` | String(30) | Not Null, Unique, Index | Formato stringa univoco (`FT-YYYY-XXXX`) |
| `tipo_documento` | String(10) | Not Null, default `'TD24'` | `'TD24'` (differita da DDT) o `'TD01'` (immediata) |
| `data_documento` | Date | Not Null | Data di emissione della fattura |
| `cliente_id` | Integer | FK `partner.id`, Not Null | Cliente intestatario della fattura |
| `condizioni_pagamento` | String(50) | Not Null, default `'30gg fm'` | Condizione per generazione rate |
| `esigibilita_iva` | String(1) | Not Null, default `'I'` | `'I'` (immediata), `'D'` (differita), `'S'` (split payment) |
| `totale_imponibile` | Float | Not Null, default `0.0` | Somma imponibile netta (€) |
| `totale_imposta` | Float | Not Null, default `0.0` | Totale IVA calcolata (€) |
| `totale_fattura` | Float | Not Null, default `0.0` | Totale documento (`imponibile + imposta`) |
| `castelletto_iva` | JSON | Nullable | Ripartizione imponibile/imposta per aliquota |
| `stato` | String(20) | Not Null, default `'emessa'` | `'bozza'`, `'emessa'`, `'inviata_sdi'`, `'saldata'` |
| `note` | Text | Nullable | Annotazioni o riferimenti bancari |

### 2.2 Tabella `invoice_item` (Righe Dettaglio Fattura)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco di riga |
| `invoice_id` | Integer | FK `invoice.id`, Not Null | Riferimento fattura (cascade delete) |
| `delivery_note_id` | Integer | FK `delivery_note.id`, Nullable | Riferimento al DDT d'origine |
| `product_id` | Integer | FK `product.id`, Not Null | Articolo fatturato |
| `descrizione` | String(200) | Not Null | Descrizione commerciale |
| `unita_misura` | String(10) | Not Null, default `'KG'` | UdM (`KG`, `PZ`, `LT`) |
| `colli` | Integer | Not Null, default `1` | Numero colli |
| `quantita` | Float | Not Null | Quantità fatturata |
| `prezzo_unitario` | Float | Not Null, default `0.0` | Prezzo unitario di vendita |
| `aliquota_iva` | Integer | Not Null, default `4` | Aliquota IVA applicata (4, 10, 22) |
| `imponibile_riga` | Float | Not Null, default `0.0` | Imponibile (`quantita * prezzo_unitario`) |
| `lotto` | String(50) | Nullable | Tracciabilità lotto bio conservata |
| `data_scadenza` | Date | Nullable | Scadenza conservata |

### 2.3 Tabella `invoice_installment` (Scadenzario Rate Pagamenti)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco rata |
| `invoice_id` | Integer | FK `invoice.id`, Not Null | Riferimento fattura (cascade delete) |
| `numero_rata` | Integer | Not Null, default `1` | Numero progressivo rata (1, 2, ...) |
| `totale_rate` | Integer | Not Null, default `1` | Numero complessivo rate |
| `data_scadenza` | Date | Not Null | Data di scadenza del pagamento |
| `importo` | Float | Not Null | Importo esatto della rata (€) |
| `stato` | String(20) | Not Null, default `'aperta'` | `'aperta'`, `'incassata'`, `'scaduta'` |
| `data_incasso` | Date | Nullable | Data in cui è stato registrato l'incasso |

---

## 3. Specifiche API REST (`backend/app.py`)

Tutti gli endpoint sono protetti con il decoratore `@require_auth()`:

- **`GET /api/delivery-notes/unbilled`**:
  - Restituisce tutti i DDT in stato `'confermato'` non ancora fatturati, raggruppabili per `cliente_id`.
- **`POST /api/invoices/from-ddt`**:
  - Parametri: `cliente_id`, `data_documento`, `condizioni_pagamento`, `ddt_ids` (array di ID DDT confermati).
  - Validazione: tutti i `ddt_ids` devono essere in stato `'confermato'` e appartenere al cliente.
  - Creazione della fattura:
    - Generazione progressivo annuale `numero_completo = f"FT-{anno}-{numero:04d}"`.
    - Clonazione delle righe dei DDT in `InvoiceItem` con valorizzazione di `delivery_note_id`.
    - Calcolo del **Castelletto IVA** aggregato per aliquota.
    - Generazione delle rate di scadenza nello scadenzario con **quadratura al centesimo**.
    - Aggiornamento di tutti i DDT inclusi a `stato = 'fatturato'`.
  - Risposta `201 Created`.
- **`GET /api/invoices`**:
  - Elenco paginato/filtrato (`stato`, `cliente_id`, `anno`, `search`).
- **`GET /api/invoices/<int:id>`**:
  - Dettaglio completo testata, righe merci e rate dello scadenzario.
- **`POST /api/invoices`**:
  - Emissione di fattura immediata manuale (`tipo_documento = 'TD01'`).
- **`GET /api/installments`**:
  - Console scadenzario con elenco di tutte le rate emesse, con filtri per stato (`aperta`, `scaduta`, `incassata`) e cliente.
- **`POST /api/installments/<int:id>/pay`**:
  - Registrazione incasso rata: imposta `stato = 'incassata'` e `data_incasso = today`.
  - Se tutte le rate della fattura risultano incassate, aggiorna automaticamente lo stato della fattura a `'saldata'`.

---

## 4. Specifiche Interfaccia Utente Quasar (`frontend/src/`)

### 4.1 Componente `Invoices.vue`
- Tabella `<q-table>` delle fatture emesse:
  - Numero (`FT-2026-0001`), Data, Cliente, Tipo (TD24/TD01), Imponibile, IVA, Totale Fattura, Stato (Emessa / Saldata).
  - Pulsante *"Fatturazione Differita da DDT"*: apre il wizard modale.
  - Pulsante *"Nuova Fattura Immediata"*.
- **Wizard Fatturazione Differita da DDT**:
  - Selezione del Cliente: interroga automaticamente `/api/delivery-notes/unbilled`.
  - Elenco con checkbox dei DDT confermati del cliente pronti da fatturare.
  - Anteprima immediata dei totali: Imponibile, IVA, Totale Fattura e piano rate calcolato.
  - Pulsante *"Emetti Fattura Differita"*.

### 4.2 Tab o Componente `InstallmentsConsole.vue` (Scadenzario Incassi)
- Tabella riepilogativa dello Scadenzario Crediti:
  - Fattura di riferimento, Cliente, Rata X/Y, Data Scadenza, Importo, Stato.
  - Chip visivi di stato: Verde (*Incassata*), Arancione (*Aperta*), Rosso (*Scaduta* se data < oggi).
  - Azione rapida *"Registra Incasso"*.

### 4.3 Navigazione Principale (`App.vue` & `router.js`)
- Nuova rotta protetta `/invoices`.
- Aggiunta della voce **"Fatture"** nella barra di navigazione principale `App.vue`.

---

## 5. Strategia di Test Automatizzati

### 5.1 Test Backend (`tests/backend/test_invoices_installments.py` - Pytest)
1. `test_invoice_differita_from_ddt`:
   - Crea e conferma un DDT, invoca `/api/invoices/from-ddt`, verifica creazione fattura TD24, clonazione righe e passaggio del DDT a `'fatturato'`.
2. `test_castelletto_iva_aggregation`:
   - Verifica calcolo e aggregazione imposte per prodotti con aliquote diverse (es. 4% ortofrutta bio e 22% imballaggi EPAL).
3. `test_installments_generation_and_quadratura`:
   - Generazione rate per pagamento `30/60gg fm` con importo dispari (es. 100.05 € -> 50.03 € e 50.02 €) verificando quadratura esatta al centesimo sul totale fattura.
4. `test_installment_payment_and_invoice_saldata`:
   - Incasso di tutte le rate e passaggio automatico della fattura da `'emessa'` a `'saldata'`.

### 5.2 Test Frontend (`tests/frontend/Invoices.spec.js` - Vitest)
1. Verifica rendering elenco fatture, badge di stato e totali.
2. Verifica caricamento DDT non fatturati nel wizard di fatturazione differita.

---

## 6. Piano di Migrazione Database
- Esecuzione migrazione Alembic nel container Docker:
  `flask db migrate -m "add invoice and installment models"`
  `flask db upgrade`
