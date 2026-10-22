# Specifica Architetturale: Vendita al Banco / Cassa Rapida (BancoM / POS) con Driver RT Pluggabile

## 1. Obiettivo e Panoramica Funzionale

Implementare nel gestionale **`erp9lli`** il modulo di **Vendita al Banco e Cassa Rapida (`BancoM` / POS)** con architettura a **Driver di Cassa Pluggabile** per la comunicazione con Registratori Telematici (RT) e stampanti termiche:
- **Interfaccia POS Touch-Friendly (`frontend/src/components/BancoM.vue`)**:
  - Selezione rapida articoli da catalogo con filtro istantaneo per nome, categoria o codice EAN/barcode;
  - Carrello della vendita con modifica immediata di quantità, prezzo al minuto, e calcolo automatico dei totali lordo, imponibile e IVA;
  - Ripartizione del pagamento (*Contanti*, *Carta / POS*, *Misto*), tastierino per banconote veloci (€5, €10, €20, €50) e calcolo in tempo reale del resto da restituire al cliente;
  - Visualizzatore e anteprima scontrino termico (formato 80mm/58mm) con matricola fiscale, intestazione aziendale e pulsante di stampa browser.
- **Tracciabilità Biologica e Scarico Magazzino FEFO**:
  - Per ogni prodotto venduto con scadenza/lotto attivo (`in_scadenza == True`), il sistema scala automaticamente la giacenza magazzino dal lotto bio più prossimo alla scadenza (logica FEFO) e ne riporta il codice sullo scontrino.
- **Driver di Cassa Pluggabile (`backend/services/pos_driver_service.py`)**:
  - Supporto a molteplici protocolli di comunicazione con i registratori fiscali italiani (RT):
    1. **`simulator` (Default dev/test)**: driver virtuale locale che simula la risposta del registratore telematico, memorizza lo scontrino e genera il testo dello scontrino per anteprima e stampa video;
    2. **`epson_epos_http`**: protocollo XML standard per registratori telematici Epson FP-81II RT / FP-90III RT tramite HTTP POST verso l'IP LAN della cassa;
    3. **`custom_tcp`**: socket TCP grezzo per stampanti fiscali Custom / RCH su porta 1999/9100;
    4. **`escpos_browser`**: emissione ricevuta termica non fiscale per stampanti da banco collegate al PC.
- **Integrazione Contabile Automatica (Partita Doppia)**:
  - All'emissione dello scontrino viene generata automaticamente la registrazione contabile di chiusura corrispettivo nel Libro Giornale (`JournalEntry`):
    - **Dare:** *Cassa Contanti* (`1.01.01.01`) o *Banca c/POS* (`1.01.02.01`);
    - **Avere:** *Merci c/Vendite al Minuto* (`4.01.01.01`);
    - **Avere:** *Erario c/IVA Vendite al Minuto* (`2.02.01.01`);
    - Quadratura contabile automatica garantita al centesimo (`Dare == Avere`).
- **Tracciamento Event Bus**:
  - Emissione evento su canale `AUDIT` con categoria `VENDITE` e tipo evento `VENDITA_BANCO`.

---

## 2. Modello Dati Relazionale (`backend/models/`)

### 2.1 Tabella `pos_station` (`backend/models/pos_station.py` - Punto Cassa)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `codice` | String(30) | Not Null, Unique, Index | Codice cassa (es. `CASSA_01`, `BANCO_01`) |
| `nome` | String(100) | Not Null | Nome descrittivo (es. "Cassa Banco Principale") |
| `driver_tipo` | String(30) | Not Null, default `'simulator'` | `'simulator'`, `'epson_epos_http'`, `'custom_tcp'`, `'escpos_browser'` |
| `ip_address` | String(50) | Nullable | Indirizzo IP LAN della cassa (es. `192.168.1.150`) |
| `porta` | Integer | Not Null, default 80 | Porta di ascolto (es. 80 per HTTP, 1999/9100 per TCP) |
| `matricola_rt` | String(50) | Nullable | Matricola fiscale AdE (es. `99MEY123456`) |
| `intestazione` | Text | Nullable | Testo di testata dello scontrino |
| `pie_pagina` | Text | Nullable | Messaggio di cortesia in calce |
| `attivo` | Boolean | Not Null, default `True` | Cassa attiva |

### 2.2 Tabella `pos_sale` (`backend/models/pos_sale.py` - Vendita al Banco)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `pos_station_id` | Integer | FK `pos_station.id`, Not Null | Cassa emittente |
| `numero_scontrino` | String(50) | Not Null, Index | Numero progressivo (es. `SC-2026-0001`) |
| `data_ora` | DateTime | Not Null, default utcnow | Timestamp emissione |
| `totale_lordo` | Numeric(12, 2) | Not Null | Totale complessivo scontrino |
| `totale_imponibile` | Numeric(12, 2) | Not Null | Totale netto imponibile |
| `totale_iva` | Numeric(12, 2) | Not Null | Totale imposta IVA |
| `metodo_pagamento` | String(30) | Not Null | `'contanti'`, `'pos_carta'`, `'misto'` |
| `importo_pagato` | Numeric(12, 2) | Not Null | Importo consegnato dall'acquirente |
| `importo_resto` | Numeric(12, 2) | Not Null, default 0.0 | Resto restituito |
| `stato` | String(20) | Not Null, default `'emesso'` | `'emesso'`, `'annullato'` |
| `stato_fiscale_rt` | String(20) | Not Null, default `'simulato'` | `'simulato'`, `'stampato'`, `'errore'` |
| `dettaglio_rt_risposta` | Text | Nullable | Esito o log della cassa RT |
| `journal_entry_id` | Integer | FK `journal_entry.id`, Nullable | Scrittura di corrispettivo in prima nota |
| `utente_email` | String(120) | Nullable | Operatore di cassa |
| `cliente_id` | Integer | FK `partner.id`, Nullable | Cliente fidelizzato opzionale |

### 2.3 Tabella `pos_sale_item` (`backend/models/pos_sale_item.py` - Righe Scontrino)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `pos_sale_id` | Integer | FK `pos_sale.id`, Not Null | Riferimento allo scontrino |
| `product_id` | Integer | FK `product.id`, Not Null | Articolo venduto |
| `quantita` | Numeric(10, 3) | Not Null | Quantità venduta |
| `prezzo_unitario` | Numeric(10, 2) | Not Null | Prezzo unitario lordo di vendita |
| `aliquota_iva` | Numeric(5, 2) | Not Null, default 22.0 | Aliquota IVA applicata (es. 4%, 10%, 22%) |
| `subtotale` | Numeric(10, 2) | Not Null | Subtotale riga |
| `lotto` | String(50) | Nullable | Lotto biologico scaricato con FEFO |
| `data_scadenza` | Date | Nullable | Data di scadenza del lotto |

---

## 3. Specifiche del Servizio Driver di Cassa (`backend/services/pos_driver_service.py`)

```python
class PosDriverService:
    @staticmethod
    def print_ticket(sale: PosSale, station: PosStation) -> dict:
        driver = station.driver_tipo or 'simulator'
        if driver == 'simulator':
            return PosDriverService._execute_simulator(sale, station)
        elif driver == 'epson_epos_http':
            return PosDriverService._execute_epson_http(sale, station)
        elif driver == 'custom_tcp':
            return PosDriverService._execute_custom_tcp(sale, station)
        else:
            return PosDriverService._execute_simulator(sale, station)
```

Il driver restituisce:
```json
{
  "success": true,
  "stato_fiscale": "simulato",
  "messaggio": "Scontrino memorizzato ed emesso con successo",
  "ticket_ascii": "--------------------------------\nRETEBIO SOCIETA' AGRICOLA\n..."
}
```

---

## 4. Specifiche API REST (`backend/app.py`)

Tutti gli endpoint richiedono `@require_auth()`:

- **`GET /api/pos/stations` & `POST /api/pos/stations`**:
  - Consultazione e censimento Punti Cassa (con seed automatico di `CASSA_01`).
- **`PUT /api/pos/stations/<int:id>`**:
  - Modifica configurazione cassa (IP, porta, tipo driver, intestazione).
- **`GET /api/pos/sales`**:
  - Elenco storico vendite al banco e scontrini emessi.
- **`POST /api/pos/sales`**:
  - Registrazione della vendita:
    1. Genera numero scontrino progressivo annuale (`SC-YYYY-XXXX`);
    2. Scarica FEFO i lotti bio per i prodotti venduti;
    3. Invoca il `PosDriverService` per la stampa/simulazione fiscale;
    4. Genera la registrazione contabile a Partita Doppia (Dare Cassa/POS, Avere Corrispettivi e IVA);
    5. Emette evento di audit a Event Bus;
    6. Restituisce HTTP 201 Created con i dettagli della vendita e il testo dello scontrino.
- **`POST /api/pos/sales/<int:id>/print`**:
  - Ristampa scontrino o riesecuzione comando driver.

---

## 5. Specifiche Interfaccia Quasar (`frontend/src/components/BancoM.vue`)

- **Schermata Cassa Touch**:
  - Colonna Sinistra: Griglia/Elenco prodotti con ricerca rapida, tasto aggiunta rapida `+`, visualizzazione prezzo e giacenza;
  - Colonna Destra: Carrello scontrino con subtotali, pulsanti incremento/decremento, selettore lotto FEFO automatico;
  - Riquadro Pagamento:
    - Selettore Contanti / Carta POS;
    - Pulsanti banconote veloci: `€5`, `€10`, `€20`, `€50`, `Esatto`;
    - Calcolo istantaneo del Resto;
  - Tasto d'impatto *"EMETTI SCONTRINO (F12)"*:
    - Apre dialog di conferma con layout realistico dello scontrino termico e pulsante di stampa browser.
- **Scheda "Storico Scontrini & Chiusura Cassa"**:
  - Tabella delle vendite della giornata con totali incassati divisi per contanti e carta POS.
- **Scheda "Configurazione Registratore Telematico (RT)"**:
  - Form per impostare Tipo Driver (Simulatore, Epson, Custom), IP e intestazione cassa.

---

## 6. Strategia di Test Automatizzati

### 6.1 Backend (`tests/backend/test_pos_bancom.py` - Pytest)
1. Persistenza modelli `PosStation`, `PosSale`, `PosSaleItem`.
2. Seed automatico del Punto Cassa `CASSA_01`.
3. Creazione vendita con scarico FEFO lotti bio e calcolo resto.
4. Generazione automatica scrittura contabile a Partita Doppia bilanciata (`Dare == Avere`).
5. Esecuzione del `PosDriverService` in modalità simulatore con generazione ticket ASCII.
6. Rifiuto vendita con importo pagato insufficiente o cassa inattiva.

### 6.2 Frontend (`tests/frontend/BancoM.spec.js` - Vitest)
1. Rendering maschera cassa BancoM con catalogo prodotti e carrello.
2. Calcolo automatico del resto al click sulle banconote.
3. Ricezione e visualizzazione dello scontrino termico emesso.
