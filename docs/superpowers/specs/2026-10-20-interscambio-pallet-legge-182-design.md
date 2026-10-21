# Specifica Architetturale: Modulo Interscambio Pallet e Buoni Pallet (Legge 182/2025)

## 1. Obiettivo e Panoramica Funzionale

Implementare nel gestionale **`erp9lli`** il modulo di **Gestione Interscambio Pallet e Imballi da Trasporto**, conforme ai requisiti della **Legge n. 182/2025** e alle procedure operative di **Gestionale ReteBio 2026** (`NewImballi`, `InvioListMailImballi`, buoni pallet):
- **Buono Pallet come Titolo di Credito Legale (`PalletReceipt`)**:
  - Emissione del documento formale numerato progressivamente per anno solare (`BP-YYYY-XXXX`).
  - Tracciamento della cessione dei bancali (EPAL, CPR 40x60, CHEP, IFCO) con indicazione del ricevente (Cliente o Vettore) e del DDT di spedizione collegato.
  - Determinazione del termine massimo di restituzione stabilito dalla legge (60 giorni o accordo commerciale fino a 90 giorni).
- **Movimentazione Resi e Partitario Saldi Dare/Avere (`PalletLedger`)**:
  - Registrazione delle restituzioni di pallet vuoti a compensazione dei buoni aperti.
  - Monitoraggio in tempo reale del **Saldo Netto di Debito/Credito** per singolo soggetto (Cliente o Vettore):
    $$\text{Saldo Pallet Debito} = \sum \text{Pallet Consegnati} - \sum \text{Pallet Restituiti}$$
  - Alert visivo per i Buoni Pallet che hanno superato il termine perentorio di restituzione.
- **Fatturazione per Mancata Restituzione in Reverse Charge**:
  - Qualora i pallet non vengano restituiti nei termini, la posizione non può restare aperta a tempo indeterminato (onde evitare rilievi di omessa fatturazione da parte dell'Agenzia delle Entrate).
  - Procedura di emissione automatica di fattura di vendita (`Invoice`, `TD01`) valorizzata al valore normale di mercato degli imballi (`valore_risarcimento`, es. 18 €/EPAL), applicando il regime di **Reverse Charge (Art. 74 comma 7/8 DPR 633/72)** per la cessione di imballaggi usati, con contestuale passaggio del Buono Pallet a stato `'fatturato'`.
- **Totale Disaccoppiamento Modulare**:
  - Il modulo fa capo al feature flag `pallets` in `AVAILABLE_MODULES`, attivabile o escludibile a piacimento senza impattare le altre aree del gestionale.

---

## 2. Modello Dati Relazionale (`backend/models/`)

### 2.1 Tabella `pallet_type` (`backend/models/pallet_type.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `codice` | String(20) | Not Null, Unique, Index | Codice formato (es. `EPAL`, `CPR_40x60`, `CPR_30x40`, `CHEP`) |
| `descrizione` | String(100) | Not Null | Descrizione completa imballo |
| `materiale` | String(20) | Not Null, default `'legno'` | `'legno'`, `'plastica'` |
| `valore_risarcimento`| Float | Not Null, default `18.00` | Valore convenzionale di risarcimento / fatturazione (€) |
| `attivo` | Boolean | Not Null, default `True` | Stato abilitazione |

### 2.2 Tabella `pallet_receipt` (`backend/models/pallet_receipt.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco Buono Pallet |
| `numero` | Integer | Not Null | Progressivo annuale (1, 2, 3...) |
| `anno` | Integer | Not Null | Anno solare di emissione (es. 2026) |
| `numero_completo` | String(30) | Not Null, Unique, Index | Formato stringa (`BP-YYYY-XXXX`) |
| `data_emissione` | Date | Not Null, default `today` | Data emissione titolo di credito |
| `data_limite_restituzione` | Date | Not Null | Scadenza perentoria restituzione (default: +60 gg) |
| `partner_id` | Integer | FK `partner.id`, Not Null | Soggetto debitore (Cliente o Vettore) |
| `delivery_note_id` | Integer | FK `delivery_note.id`, Nullable | Eventuale DDT di spedizione merci abbinato |
| `tipo` | String(20) | Not Null, default `'uscita'` | `'uscita'` (consegna pallet), `'rientro'` (reso vuoti) |
| `totale_consegnati` | Integer | Not Null, default `0` | Somma pallet ceduti |
| `totale_restituiti` | Integer | Not Null, default `0` | Somma pallet contestualmente restituiti |
| `saldo_netto` | Integer | Not Null, default `0` | Saldo Buono (`consegnati - restituiti`) |
| `stato` | String(20) | Not Null, default `'aperto'` | `'aperto'`, `'saldato'`, `'fatturato'` |
| `note` | Text | Nullable | Annotazioni o firma conducente |

### 2.3 Tabella `pallet_receipt_item` (`backend/models/pallet_receipt_item.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco riga |
| `pallet_receipt_id`| Integer | FK `pallet_receipt.id`, Not Null | Riferimento testata buono (cascade delete) |
| `pallet_type_id` | Integer | FK `pallet_type.id`, Not Null | Formato pallet/imballo |
| `quantita_consegnata`| Integer | Not Null, default `0` | Pezzi consegnati al ricevente |
| `quantita_restituita`| Integer | Not Null, default `0` | Pezzi restituiti dal ricevente |
| `saldo_riga` | Integer | Not Null, default `0` | Saldo riga (`consegnata - restituita`) |

---

## 3. Specifiche API REST (`backend/app.py`)

Tutti gli endpoint richiedono `@require_auth()`:

- **`GET /api/pallets/types` & `POST /api/pallets/types`**:
  - Gestione anagrafica formati pallet e valori di risarcimento.
- **`GET /api/pallets/receipts`**:
  - Elenco Buoni Pallet emessi con filtri per `partner_id`, `stato` (`aperto`, `saldato`, `fatturato`), `anno`, `search`.
- **`GET /api/pallets/receipts/<id>`**:
  - Dettaglio completo testata, righe, giorni alla scadenza legale e riferimenti DDT.
- **`POST /api/pallets/receipts`**:
  - Emissione nuovo Buono Pallet con numerazione `BP-YYYY-XXXX`, calcolo automatico dei saldi e impostazione data limite a +60 giorni.
- **`POST /api/pallets/receipts/<id>/return`**:
  - Registrazione restituzione pallet vuoti a compensazione del buono aperto. Se il saldo netto raggiunge 0, aggiorna lo stato del buono a `'saldato'`.
- **`GET /api/pallets/ledger`**:
  - Prospetto partitario saldi pallet raggruppato per Soggetto (`partner_id`) e Tipo Pallet, con calcolo dei pezzi complessivi a debito e segnalazione dei buoni scaduti.
- **`POST /api/pallets/receipts/<id>/invoice-unreturned`**:
  - Procedura di **Fatturazione per Mancata Restituzione**:
    - Calcola l'importo totale moltiplicando i pezzi a debito per il `valore_risarcimento`.
    - Genera una fattura immediata (`Invoice`, `TD01`) intestata al partner con imponibile, aliquota IVA 0% e dicitura doganale/fiscale:
      *"Cessione imballaggi usati non restituiti ex L. 182/2025 - Operazione in Reverse Charge ai sensi dell'Art. 74 c. 7/8 DPR 633/72"*.
    - Aggiorna lo stato del Buono Pallet a `'fatturato'`.

---

## 4. Specifiche Interfaccia Utente Quasar (`frontend/src/`)

### 4.1 Componente `Pallets.vue`
- Organizzato in 3 schede:
  1. **Buoni Pallet (`BP-2026-xxxx`)**:
     - Tabella con data, numero buono, partner, consegnati, resi, saldo e chip stato (*Aperto* arancione, *Saldato* verde, *Fatturato* blu).
     - Badge giorni alla scadenza legale (rosso se oltre 60 giorni).
     - Pulsante *"Nuovo Buono Pallet"* e azione rapida *"Registra Reso"*.
  2. **Partitario Saldi Pallet**:
     - Tabella riassuntiva dei crediti pallet verso Clienti e Vettori (totale EPAL e CPR in debito).
     - Azione rapida *"Fattura Mancata Resa (Reverse Charge)"* per i buoni scaduti.
  3. **Tipologie Pallet**:
     - Configurazione formati, materiali e valori di risarcimento.

### 4.2 Navigazione & Feature Flag (`App.vue` & `router.js`)
- Registrazione del modulo `"pallets"` in `AVAILABLE_MODULES`.
- Voce **"Interscambio Pallet (L.182)"** nella sidebar sotto il gruppo *Logistica & Magazzino*, visibile con `v-if="activeModules.pallets"`.
- Rotta protetta `/pallets` registrata in `router.js`.

---

## 5. Strategia di Test Automatizzati

### 5.1 Test Backend (`tests/backend/test_pallets_interchange.py` - Pytest)
1. `test_pallet_type_and_receipt_models`: verifica persistenza modelli e relazioni.
2. `test_create_pallet_receipt_sequential_and_term`: verifica emissione `BP-YYYY-XXXX` e calcolo scadenza 60 giorni.
3. `test_pallet_receipt_return_and_settlement`: restituzione pallet con passaggio a stato `'saldato'` quando saldo = 0.
4. `test_pallet_ledger_balances`: verifica calcolo saldi netti per soggetto nel partitario.
5. `test_invoice_unreturned_pallets_reverse_charge`: verifica generazione fattura TD01 con causale Reverse Charge e chiusura buono a `'fatturato'`.

### 5.2 Test Frontend (`tests/frontend/Pallets.spec.js` - Vitest)
1. Verifica rendering schede Buoni Pallet, partitario saldi e calcolo giorni scadenza.

---

## 6. Piano di Migrazione Database
- Esecuzione migrazione Alembic nel container Docker:
  `flask db migrate -m "add pallet interchange models"`
  `flask db upgrade`
