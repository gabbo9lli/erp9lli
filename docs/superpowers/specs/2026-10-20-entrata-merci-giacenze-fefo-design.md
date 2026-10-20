# Specifica Architetturale: Modulo Entrata Merci da Fornitori e Gestione Giacenze Magazzino FEFO

## 1. Obiettivo e Panoramica Funzionale

Completare la gestione della Supply Chain per **`erp9lli`** introducendo il modulo **`warehouse`** (Entrata Merci da Fornitori & Giacenze con logica FEFO), conforme ai requisiti di tracciabilità biologica di **Gestionale ReteBio 2026** (`T_MOV` carichi fornitore, `T_MovR` lotti, calcolo giacenze):
- **Entrata Merci da Fornitori (`PurchaseDeliveryNote` & `PurchaseDeliveryNoteItem`)**:
  - Registrazione delle bolle/DDT di acquisto emesse dai produttori biologici.
  - Preservazione obbligatoria dei parametri di filiera deperibile: **Lotto Fornitore** e **Data di Scadenza** per gli articoli con `in_scadenza == True`.
  - Aggiornamento istantaneo del costo di acquisto unitario nell'anagrafica articolo (`Product.prezzo_acquisto`).
- **Cruscotto Giacenze di Magazzino in Tempo Reale**:
  - Calcolo dinamico della disponibilità per combinazione `(Articolo, Lotto)`:
    $$\text{Giacenza}(art, lotto) = \sum \text{Carichi da Fornitori} - \sum \text{Scarichi su DDT di Vendita}$$
  - Monitoraggio visivo dello stato di freschezza del lotto:
    - 🟢 **Verde (Fresco)**: scadenza > 15 giorni.
    - 🟡 **Giallo (In Scadenza)**: scadenza tra 1 e 15 giorni.
    - 🔴 **Rosso (Scaduto o Critico)**: scadenza $\le 0$ giorni.
- **Motore di Suggerimento FEFO (First Expired, First Out)**:
  - In fase di preparazione delle Bolle di Vendita (DDT) o evasione ordini, l'operatore riceve l'elenco dei lotti disponibili ordinati per:
    $$\text{ORDER BY data\_scadenza ASC, data\_ricezione ASC}$$
  - Selezione immediata del lotto con scadenza più prossima per ridurre gli sprechi e azzerare i resi.
- **Totale Disaccoppiamento Modulare (Loose Coupling)**:
  - Il modulo `warehouse` è governato dal feature flag `ENABLED_MODULES` e dalla configurazione dell'istanza.
  - La Bollettazione DDT e la Fatturazione continuano a funzionare autonomamente anche in installazioni prive del modulo magazzino.

---

## 2. Modello Dati Relazionale (`backend/models/`)

### 2.1 Tabella `purchase_delivery_note` (`backend/models/purchase_delivery_note.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `numero_documento_fornitore` | String(50) | Not Null, Index | Numero del DDT emesso dal fornitore |
| `data_documento` | Date | Not Null | Data emissione DDT fornitore |
| `data_ricezione` | Date | Not Null, default `today` | Data di arrivo fisico della merce a magazzino |
| `fornitore_id` | Integer | FK `partner.id`, Not Null | Fornitore / Produttore biologico |
| `colli_totali` | Integer | Not Null, default `0` | Somma colli ricevuti |
| `peso_totale_netto` | Float | Not Null, default `0.0` | Totale Kg netti ricevuti |
| `totale_imponibile` | Float | Not Null, default `0.0` | Valore merce acquistata (€) |
| `note` | Text | Nullable | Note su controllo qualità all'arrivo |

### 2.2 Tabella `purchase_delivery_note_item` (`backend/models/purchase_delivery_note_item.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco di riga |
| `purchase_delivery_note_id` | Integer | FK `purchase_delivery_note.id`, Not Null | Riferimento testata (cascade delete) |
| `product_id` | Integer | FK `product.id`, Not Null | Articolo ricevuto |
| `descrizione` | String(200) | Not Null | Descrizione articolo |
| `unita_misura` | String(10) | Not Null, default `'KG'` | UdM (`KG`, `PZ`) |
| `colli` | Integer | Not Null, default `1` | Numero colli caricati |
| `quantita` | Float | Not Null | Quantità ricevuta (Kg netti) |
| `prezzo_unitario` | Float | Not Null, default `0.0` | Prezzo di acquisto unitario (€) |
| `aliquota_iva` | Integer | Not Null, default `4` | Aliquota IVA (4% ortofrutta bio) |
| `lotto` | String(50) | Nullable | Lotto fornitore (**obbligatorio** se `in_scadenza`) |
| `data_scadenza` | Date | Nullable | Scadenza biologica (**obbligatorio** se `in_scadenza`) |

---

## 3. Specifiche API REST (`backend/app.py`)

Tutte le rotte richiedono `@require_auth()`:

- **`GET /api/purchases`**:
  - Parametri filtro: `fornitore_id`, `data_inizio`, `data_fine`, `search`.
  - Restituisce l'elenco dei carichi fornitore con totali colli e pesi.
- **`GET /api/purchases/<id>`**:
  - Dettaglio completo testata e righe carico con lotti e date scadenza.
- **`POST /api/purchases`**:
  - Registrazione carico fornitore.
  - Validazione: se un prodotto ha `in_scadenza == True`, impone `lotto` e `data_scadenza` non nulli (altrimenti `400 Bad Request`).
  - Aggiornamento facoltativo del prezzo di acquisto di default sul prodotto.
- **`GET /api/warehouse/stock`**:
  - Raggruppa tutti i carichi fornitori e sottrae tutti gli scarichi da DDT vendite per combinazione `(product_id, lotto)`.
  - Calcola: `giacenza_kg`, `colli_disponibili`, `data_scadenza`, `giorni_a_scadere`, `stato_scadenza` (`fresco`, `in_scadenza`, `scaduto`).
- **`GET /api/warehouse/fefo-suggestions?product_id=X`**:
  - Restituisce la lista dei lotti dell'articolo con giacenza $> 0$ ordinati per `data_scadenza ASC`.
  - Indica il lotto consigliato FEFO per la vendita.

---

## 4. Specifiche Interfaccia Utente Quasar (`frontend/src/`)

### 4.1 Componente `Purchases.vue` (Entrata Merci Fornitori)
- Tabella delle bolle d'acquisto ricevute: Fornitore, Data Arrivo, Doc Fornitore, Colli, Peso Netto, Totale €.
- Pulsante *"Registra Carico Merci"*:
  - Form con selezione fornitore, estremi bolla e righe dinamiche con colli, quantità, prezzo acquisto e campi obbligatori per lotto bio e data scadenza.

### 4.2 Componente `WarehouseStock.vue` (Giacenze & Lotti FEFO)
- Cruscotto scorte con filtri per categoria e ricerca articolo.
- Tabella articoli con espansione dettaglio lotti:
  - Codice articolo, Descrizione, Giacenza Totale Kg.
  - Sotto-tabella lotti: Codice Lotto, Data Arrivo, Data Scadenza, Giorni Rimanenti, Badge semaforico colorato, Giacenza Residua Kg.

### 4.3 Integrazione in `DeliveryNotes.vue` (Suggerimento FEFO su Bolle Vendita)
- Nella modale di creazione DDT vendita, accanto al campo lotto compare il pulsante *"Suggerisci Lotto FEFO"*:
  - Cliccandolo, il sistema seleziona istantaneamente il lotto in scadenza più vicina con giacenza disponibile.

### 4.4 Sidebar e Navigazione Dinamica (`App.vue` & `router.js`)
- Registrazione modulo `"warehouse"` in `AVAILABLE_MODULES`.
- Se `activeModules.warehouse == true`, compare nel menu laterale il gruppo:
  - 📥 **Entrata Merci (Carichi)** (`/purchases`)
  - 📦 **Giacenze Magazzino FEFO** (`/warehouse`)
- Rotte protette in `router.js` per `/purchases` e `/warehouse`.

---

## 5. Strategia di Test Automatizzati

### 5.1 Test Backend (`tests/backend/test_warehouse_fefo.py`)
1. `test_create_purchase_delivery_note_validation`: verifica registrazione carico fornitore e validazione obbligatorietà lotto/scadenza per prodotti freschi.
2. `test_stock_running_calculation`: carico di 200 Kg fornitore per LOTTO-A, scarico di 60 Kg su DDT vendita -> giacenza risultante esattamente 140 Kg.
3. `test_fefo_suggestion_ordering`: carico di LOTTO-1 (scadenza 10/11) e LOTTO-2 (scadenza 25/11) -> l'endpoint FEFO suggerisce per primo LOTTO-1.
4. `test_loose_coupling_delivery_notes_without_warehouse`: verifica che l'emissione del DDT di vendita funzioni regolarmente anche senza dati di magazzino fornitore.

### 5.2 Test Frontend (`tests/frontend/WarehouseStock.spec.js`)
1. Verifica rendering tabella giacenze, calcolo badge di stato scadenza e presenza filtri.

---

## 6. Piano di Migrazione Database
- Esecuzione migrazione Alembic nel container Docker:
  `flask db migrate -m "add purchase delivery note models"`
  `flask db upgrade`
