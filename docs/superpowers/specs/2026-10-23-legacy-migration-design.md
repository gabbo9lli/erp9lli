# Spec: Modulo Inizializzazione e Migrazione Dati da Gestionale Legacy Access (ReteBio)

**Data:** 23 Ottobre 2026  
**Autore:** Team di Sviluppo erp9lli  
**Stato:** Approvato (Pronto per Piano di Implementazione)  
**Percorso Documento:** `docs/superpowers/specs/2026-10-23-legacy-migration-design.md`  

---

## 1. Obiettivo e Contesto

L'obiettivo è dotare **erp9lli** di un modulo di migrazione e inizializzazione dati in grado di acquisire l'intero patrimonio informativo dal precedente ERP aziendale Microsoft Access (`GestionaleReteBio2026.accdb` situato in `/Users/novellig/docker_images/gestionale_retebio/` o database di annate storiche precedenti come `2024_DB.accdb`, `2025_DB.accdb`).

Il modulo deve garantire due requisiti operativi imprescindibili:
1. **Inizializzazione Ripetibile da Zero (Wipe & Load):** Possibilità di azzerare in modo sicuro e transazionale il database operativo e rieseguire l'importazione da zero quante volte necessario durante i collaudi o l'avviamento in produzione, preservando le credenziali dell'amministratore per evitare blocchi;
2. **Importazione Incrementale e Idempotente (Merge & Append):** Possibilità di importare ulteriori database annuali pregressi o archiviati senza duplicare le anagrafiche già presenti (clienti, fornitori, articoli biologici) e garantendo la quadratura contabile e documentale.

---

## 2. Architettura Tecnica e Componenti

Il modulo rispetta la Clean Architecture a 4 livelli consolidata in erp9lli:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. UI Layer: frontend/src/components/LegacyMigration.vue               │
│    - Scansione e anteprima record (Dry Run)                            │
│    - Selettore modalità: Inizializzazione (Reset) vs Incrementale      │
│    - Monitoraggio avanzamento in tempo reale tramite WebSocket         │
├────────────────────────────────────────────────────────────────────────┤
│ 2. API Transport Layer: backend/api/routers/migration.py               │
│    - POST /api/migration/inspect       (Verifica e lettura tabelle)    │
│    - POST /api/migration/dry-run      (Simulazione volumi ed errori)   │
│    - POST /api/migration/reset        (Wipe atomico con safety token)  │
│    - POST /api/migration/execute      (Esecuzione reale asincrona)     │
├────────────────────────────────────────────────────────────────────────┤
│ 3. DTO & Validation Layer: backend/schemas/migration.py                │
│    - MigrationInspectRequest, MigrationInspectResponse                 │
│    - MigrationDryRunResponse, MigrationExecuteRequest                  │
├────────────────────────────────────────────────────────────────────────┤
│ 4. Domain Service: backend/services/legacy_migration_service.py        │
│    - Wrapper MDB tools (`/opt/homebrew/bin/mdb-export` o `mdb-export`) │
│    - Motore di trasformazione e sanitizzazione campi Access            │
│    - Gestione tabelle storiche Access: T_AllaDataFA, Tabella1CReg, T2  │
│    - Riconciliazione entità e registro `LegacyMigrationSync`           │
├────────────────────────────────────────────────────────────────────────┤
│ 5. Persistence: backend/models/legacy_migration_sync.py                │
│    - Modello ORM SQLAlchemy `LegacyMigrationSync`                      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Modello Dati di Tracciamento: `LegacyMigrationSync`

Per garantire l'idempotenza e consentire caricamenti incrementali senza duplicazioni, viene introdotto il modello `LegacyMigrationSync` nella cartella `backend/models/`:

### Struttura Tabella `legacy_migration_sync`:
| Campo | Tipo | Descrizione |
|---|---|---|
| `id` | Integer (PK) | Identificativo univoco del record di sincronizzazione |
| `source_file` | String(255) | Nome file sorgente (es. `GestionaleReteBio2026.accdb`) |
| `entity_type` | String(50) | Tipologia entità (`partner`, `product`, `stock_lot`, `invoice`, `installment`) |
| `legacy_id` | String(100) | ID primario originale in Access (`IdCliente`, `IdArt`, `IdFF`, `IDScad`) |
| `target_id` | Integer | ID corrispondente nel database PostgreSQL di erp9lli |
| `anno` | Integer (nullable) | Anno di riferimento per i documenti contabili |
| `created_at` | DateTime | Timestamp del primo inserimento |
| `updated_at` | DateTime | Timestamp dell'ultimo aggiornamento |

**Vincolo Univoco:** `UniqueConstraint('source_file', 'entity_type', 'legacy_id', name='uq_legacy_sync_source_entity_id')`

---

## 4. Mappatura ed Estrazione dalle Tabelle Access

L'analisi svolta sul database `GestionaleReteBio2026.accdb` individua le seguenti tabelle primarie per la migrazione:

### 4.1 Soggetti Commerciali (`Partner`)
- **Tabelle Sorgente:** `T_AllaDataFA` (`IdCliente`, `RagSoc`), `FattureElMese` (`IdCliente`, `RagSoc`, `Nazione`) e produttori agricoli (`produttore`).
- **Regole di Mappatura:**
  - `ragione_sociale`: testo ripulito da spazi multipli e apici anomali;
  - `tipo`: `'cliente'` per gli acquirenti/committenti; `'fornitore'` per i produttori di conferimento agricolo;
  - `partita_iva` e `codice_fiscale`: estratti se presenti o lasciati nulli se non valorizzati nella testata storica;
  - `nazione`: se `"italia"` o stringa vuota ➔ `"IT"`, altrimenti codice bilingue ISO 2 caratteri (`BE`, `DE`, `FR`);
  - `attivo`: `True`.
- **Idempotenza:** Se il partner è già presente (verificato tramite `LegacyMigrationSync` o per `ragione_sociale` esatta), viene recuperato il `target_id` esistente senza creare duplicati.

### 4.2 Catalogo Articoli Biologici (`Product`)
- **Tabelle Sorgente:** `Tabella1CReg` e `T_AllaDataFA` (`IdArt`, `CodArt`, `DescArt`, `um`, `prezzoArt`, `IVA`, `CodiceNC`).
- **Regole di Mappatura:**
  - `codice`: `CodArt` (es. `BIO-ARAN-TRC`, `CLM-FM`, `LMNA-MA`); se nullo, generato come `ART-LEGACY-{IdArt}`;
  - `descrizione`: `DescArt` normalizzato;
  - `categoria`: se la descrizione o il tipo indica casse/imballaggi ➔ `'imballo'`, altrimenti `'fresco'`;
  - `unita_misura`: conversione di `N.` in `PZ`, default `KG` per prodotti pesati;
  - `in_scadenza`: `True` per tutti i prodotti biologici deperibili;
  - `prezzo_vendita`: `prezzoArt` float con arrotondamento a 2 decimali;
  - `prezzo_acquisto`: `prezzoArt * 0.70` (se non presente acquisto specifico);
  - `aliquota_iva`: se specificata `IVA` (es. 4, 10, 22), altrimenti default 4% per ortofrutta;
  - `codice_nc`: codice doganale per l'esportazione (es. `39231090`, `08051020`);
  - `attivo`: `True`.
- **Idempotenza:** Chiave univoca su `codice` articolo o corrispondenza in `LegacyMigrationSync(entity_type='product', legacy_id=IdArt)`.

### 4.3 Giacenze di Magazzino e Lotti Iniziali (`Stock`)
- **Tabella Sorgente:** `T2` (`IdArt`, `ScadenzaR`, `lotto`, `totgiac`).
- **Regole di Mappatura:**
  - Ogni record di `T2` con `totgiac > 0` genera un carico iniziale di inventario;
  - Viene creata una testata `PurchaseDeliveryNote`:
    - `numero_documento_fornitore`: `INVENTARIO-INIZIALE-LEGACY`
    - `data_ricezione`: data odierna
    - `fornitore_id`: fornitore predefinito interno (o primo fornitore disponibile)
  - Per ciascuna riga viene creato `PurchaseDeliveryNoteItem`:
    - `product_id`: `target_id` del prodotto associato
    - `quantita`: `totgiac`
    - `lotto`: `lotto` (es. `LT 26/50`, `LT 4 26`)
    - `data_scadenza`: `ScadenzaR` formattata come data ISO
- **Idempotenza:** Se il carico di inventario iniziale per quel prodotto e lotto esiste già, non viene duplicato.

### 4.4 Fatture Attive Storiche (`Invoice` & `InvoiceItem`)
- **Tabella Sorgente:** `T_AllaDataFA` (raggruppata per `IdFF`: `NFatt`, `datafatt`, `IdCliente`).
- **Regole di Mappatura:**
  - `numero`: intero derivato da `NFatt`;
  - `anno`: anno derivato da `datafatt`;
  - `numero_completo`: `f"FT-{anno}-{numero:04d}"`;
  - `tipo_documento`: `'TD01'` (o `'TD24'` se differita);
  - `data_documento`: data parsata da `datafatt`;
  - `cliente_id`: `target_id` del partner mappato;
  - `totale_imponibile`, `totale_imposta`, `totale_fattura`: calcolati sommando le righe `totriga`;
  - `stato`: `'emessa'` (o `'saldata'` se le rate sono tutte incassate);
  - Righe `InvoiceItem`: create per ciascuna riga di `T_AllaDataFA` con prodotto, quantità, prezzo unitario e imponibile.
- **Idempotenza:** Chiave `(tipo_documento, anno, numero)`.

### 4.5 Scadenzario Incassi (`InvoiceInstallment`)
- **Tabella Sorgente:** `ScadenzarioPRT` e `AllaDataTutto` (`idscad`, `idff`, `numerofattura`, `datafattura`, `scadenza`, `importoscadenza`, `saldo`, `pagato`, `datapagamento`).
- **Regole di Mappatura:**
  - Collegamento alla fattura corrispondente (`Invoice`);
  - `numero_rata`: progressivo riga rata;
  - `data_scadenza`: `scadenza` parsata;
  - `importo`: float di `importoscadenza`;
  - `stato`: `'incassata'` se `pagato == 1` o `saldo <= 0.01`, altrimenti `'aperta'`;
  - `data_incasso`: `datapagamento` se pagato.

---

## 5. Procedura di Reset ("Wipe Controllato")

Per garantire che l'operazione possa essere rifatta da zero quante volte necessario:

### Endpoint: `POST /api/migration/reset`
* **Payload di autorizzazione:**
  ```json
  {
    "confirm_wipe": "RESET_ERP9LLI"
  }
  ```
* **Comportamento atomico (in una singola transazione DB):**
  1. Truncate con cascade o delete ordinato di:
     - `journal_items`, `journal_entries`
     - `invoice_installments`, `invoice_items`, `invoices`
     - `cmr_items`, `cmr_documents`
     - `delivery_note_items`, `delivery_notes`
     - `order_items`, `customer_orders`
     - `purchase_delivery_note_items`, `purchase_delivery_notes`
     - `pallet_receipt_items`, `pallet_receipts`
     - `pos_sale_items`, `pos_sales`
     - `ecommerce_sync_logs`, `system_events`
     - `legacy_migration_sync`
     - `products`, `partners`
  2. **Condizione di Salvaguardia:** La tabella `users` **NON** viene mai toccata. L'amministratore autenticato mantiene la sessione e il login attivi.
  3. Re-inizializzazione dei dati base di sistema (Piano dei Conti CEE e Causali Contabili standard).

---

## 6. Modalità Esecutiva e Notifiche Real-Time

1. **Dry-Run (`POST /api/migration/dry-run`):**
   - Esegue la scansione senza scrivere nel database;
   - Restituisce un report statistico:
     ```json
     {
       "source_file": "GestionaleReteBio2026.accdb",
       "partners_count": 195,
       "products_count": 3210,
       "stock_lots_count": 324,
       "invoices_count": 896,
       "installments_count": 1675,
       "estimated_seconds": 15
     }
     ```
2. **Esecuzione Asincrona (`POST /api/migration/execute`):**
   - Lanciata come background task tramite `event_dispatcher`;
   - Emette aggiornamenti di progresso via WebSocket:
     - 15%: Estrazione e importazione Partner;
     - 45%: Estrazione e importazione Catalogo Prodotti;
     - 65%: Carico iniziale giacenze e lotti (T2);
     - 85%: Importazione fatture e relative righe;
     - 95%: Riconciliazione scadenze e partitari;
     - 100%: Completamento e salvataggio indice `LegacyMigrationSync`.

---

## 7. Interfaccia Grafica Utente (`LegacyMigration.vue`)

Una nuova pagina amministrativa posizionata in `frontend/src/components/LegacyMigration.vue` e registrata nel router su `/legacy-migration`:
- **Card Parametri Sorgente:** Percorso del file Access (default `/Users/novellig/docker_images/gestionale_retebio/GestionaleReteBio2026.accdb`);
- **Selettore Modalità:**
  - [x] *Importazione Incrementale (Consigliata - aggiorna e inserisce senza cancellare)*
  - [ ] *Inizializzazione da Zero (Attiva dialog di conferma con inserimento frase di sicurezza)*
- **Card Anteprima / Statistiche:** Visualizzazione dei conteggi ricavati dal dry-run;
- **Card Avanzamento Live:** Barra di progresso sincronizzata con i WebSockets e terminale log con gli eventi migrati in streaming.

---

## 8. Piano di Test e Validazione

1. **Test Backend Pytest (`tests/backend/test_legacy_migration.py`):**
   - Test del parsing Access e conversione tipi;
   - Test di esecuzione `dry-run` su file esistente;
   - Test di `reset`: verifica che le tabelle transazionali siano azzerate e che `User` admin rimanga presente;
   - Test di idempotenza: esecuzione di due importazioni consecutive e verifica che i conteggi delle entità rimangano identici senza errori di chiave duplicata;
   - Test di ricezione evento WebSocket durante la migrazione.
2. **Test Frontend Vitest (`tests/frontend/LegacyMigration.spec.js`):**
   - Test di rendering dell'interfaccia e dei selettori di modalità;
   - Test di invocazione del dry-run e visualizzazione della tabella statistiche;
   - Test della dialog di sicurezza per la modalità Reset;
   - Test di reattività con ricezione messaggi WebSocket per avanzamento barra.
