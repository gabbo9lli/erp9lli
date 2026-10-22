# Specifica Architetturale: Anagrafica Causali Contabili Operative (AccountingCausal), Allineamento Automatico Partita Doppia ed Event Bus

## 1. Obiettivo e Panoramica Funzionale

Implementare nel gestionale **`erp9lli`** l'**Anagrafica delle Causali Contabili Operative (`AccountingCausal`)** e l'**Allineamento Automatico Totale di Partita Doppia, Movimenti ed Event Bus**:
- **Anagrafica Causali Contabili Operative (`AccountingCausal`)**:
  - Modello relazionale a database che censisce i codici causale (es. `VEND_FATT`, `VEND_NC`, `INCASSO_RATA`, `CORRISPETTIVO`, `ACQ_MERCI`, `PAGAM_FORN`);
  - Per ciascuna causale definisce in modo dinamico i conti predefiniti:
    - **`conto_dare_id`** (es. `1101` Crediti Clienti, `1002` Banca c/c);
    - **`conto_avere_id`** (es. `4101` Ricavi Vendite, `1101` Crediti Clienti);
    - **`conto_iva_id`** (es. `2201` IVA a Debito, `2202` IVA a Credito);
    - **`tipo_registro`** (`vendite`, `acquisti`, `corrispettivi`, `generale`);
    - **`template_descrizione`** (es. `"Fattura n. {numero} a {cliente}"`);
  - Elimina ogni codice conto cablato rigidamente nel codice Python (`Account.query.filter_by(codice="1001")`), permettendo all'amministratore di variare i conti e le causali direttamente da interfaccia utente.
- **Associazione Dichiarativa tra Eventi di Sistema e Causali**:
  - Il modello `EventType` viene esteso con `accounting_causal_id`: ciascun evento di business dichiara quale causale contabile azionare automaticamente.
- **Allineamento Automatico Totale in Partita Doppia**:
  - **Emissione Fatture (TD01 / TD24)**: genera automaticamente la registrazione in prima nota (`JournalEntry` Dare Crediti Clienti, Avere Ricavi e IVA) con quadratura a pareggio vincolante;
  - **Incasso Rate Scadenzario (`pay_installment`)**: genera automaticamente la scrittura contabile di incasso (Dare Banca/Cassa, Avere Crediti Clienti) e chiude la partita aperta;
  - **Note di Credito (TD04)**: genera automaticamente la scrittura di storno (Dare Ricavi e IVA, Avere Crediti Clienti);
  - **Vendita al Banco (POS)**: legge dinamicamente i conti dalla causale `CORRISPETTIVO`.
- **Emissione Sistematica su Event Bus**:
  - Ogni allineamento automatico emette formalmente un evento tracciato con `dispatch_event` su canale `AUDIT` con il payload contenente i riferimenti incrociati (`documento_id`, `journal_entry_id`, `importo`, `cliente_id`), garantendo visibilità immediata in `ActivityCenter.vue`.
- **Interfaccia Quasar (`frontend/src/components/Accounting.vue`)**:
  - Nuova scheda **"Causali Contabili & Automatismi"** per visualizzare e modificare il mapping dei conti;
  - Nella maschera di Prima Nota manuale, selezione a tendina della causale con auto-compilazione immediata dei conti Dare e Avere.

---

## 2. Modello Dati Relazionale (`backend/models/`)

### 2.1 Tabella `accounting_causal` (`backend/models/accounting_causal.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `codice` | String(30) | Not Null, Unique, Index | Codice causale (es. `VEND_FATT`, `INCASSO_RATA`, `VEND_NC`) |
| `descrizione` | String(150) | Not Null | Descrizione formale operazione |
| `tipo_registro` | String(30) | Not Null, default `'generale'` | `'vendite'`, `'acquisti'`, `'corrispettivi'`, `'generale'` |
| `conto_dare_id` | Integer | FK `account.id`, Nullable | Conto predefinito in Dare |
| `conto_avere_id` | Integer | FK `account.id`, Nullable | Conto predefinito in Avere |
| `conto_iva_id` | Integer | FK `account.id`, Nullable | Conto predefinito IVA |
| `template_descrizione` | String(200) | Nullable | Template causale (es. `"Fattura {numero} del {data}"`) |
| `attivo` | Boolean | Not Null, default `True` | Causale abilitata |

### 2.2 Estensioni dei Modelli Esistenti
- **`EventType` (`backend/models/event_type.py`)**:
  - Aggiunta colonna `accounting_causal_id`: FK `accounting_causal.id`, nullable;
  - Relazione `accounting_causal = db.relationship('AccountingCausal')`.
- **`JournalEntry` (`backend/models/journal_entry.py`)**:
  - Aggiunta colonna `causale_id`: FK `accounting_causal.id`, nullable;
  - Relazione `causale_obj = db.relationship('AccountingCausal')`.

---

## 3. Seed delle Causali Operative Standard (`seed_accounting.py`)

All'avvio vengono censite e collegate ai conti CEE le 6 causali operative:
1. `VEND_FATT`: Dare `1101` (Crediti Clienti), Avere `4101` (Ricavi Vendite Bio), IVA `2201` (Erario c/IVA Debito).
2. `VEND_NC`: Dare `4101` (Ricavi Vendite Bio), Avere `1101` (Crediti Clienti), IVA `2201` (Erario c/IVA Debito).
3. `INCASSO_RATA`: Dare `1002` (Banca c/c Principale), Avere `1101` (Crediti Clienti).
4. `CORRISPETTIVO`: Dare `1001` (Cassa Contanti), Avere `4101` (Ricavi Vendite Bio), IVA `2201` (Erario c/IVA Debito).
5. `ACQ_MERCI`: Dare `5101` (Costi Merci Acquisti), Avere `2001` (Debiti Fornitori), IVA `2202` (Erario c/IVA Credito).
6. `PAGAM_FORN`: Dare `2001` (Debiti Fornitori), Avere `1002` (Banca c/c Principale).

Associazione automatica a `EventType`:
- `EMISSIONE_FATTURA.accounting_causal_id` $\rightarrow$ `VEND_FATT.id`
- `INCASSO_RATA.accounting_causal_id` $\rightarrow$ `INCASSO_RATA.id`
- `CARICO_MERCI.accounting_causal_id` $\rightarrow$ `ACQ_MERCI.id`

---

## 4. Specifiche API REST (`backend/app.py`)

Tutti gli endpoint richiedono `@require_auth()`:

- **`GET /api/accounting/causals`**:
  - Restituisce l'elenco delle causali contabili con i conti Dare, Avere e IVA collegati.
- **`POST /api/accounting/causals`**:
  - Censimento di una nuova causale (richiede ruolo `Admin`).
- **`PUT /api/accounting/causals/<int:id>`**:
  - Modifica della mappatura conti dare/avere/iva o descrizione (richiede ruolo `Admin`).
- **Integrazione in `POST /api/invoices`**:
  - Genera `JournalEntry` con causale `VEND_FATT` (o configurata in `EventType`), bilanciando al centesimo Dare/Avere.
  - Invia `dispatch_event(event_type_code="EMISSIONE_FATTURA", ...)`.
- **Integrazione in `POST /api/installments/<id>/pay`**:
  - Genera `JournalEntry` con causale `INCASSO_RATA` (Dare Banca, Avere Crediti Clienti).
  - Invia `dispatch_event(event_type_code="INCASSO_RATA", ...)`.
- **Integrazione in `POST /api/invoices/<id>/credit-note`**:
  - Genera `JournalEntry` con causale `VEND_NC` (Storno ricavi/iva).
  - Invia `dispatch_event(event_type_code="EMISSIONE_FATTURA", ...)`.

---

## 5. Specifiche Interfaccia Quasar (`Accounting.vue`)

- **Scheda "Causali Contabili & Mappatura"**:
  - Tabella con tutte le causali censite;
  - Selettori per visualizzare e modificare rapidamente conto Dare, Avere e IVA;
  - Pulsante per aggiungere nuove causali per operazioni contabili personalizzate.
- **Dialog "Nuova Scrittura Prima Nota"**:
  - Menu a tendina per selezionare la causale:
  - Al cambio di selezione, auto-compilazione automatica dei conti Dare e Avere impostati nella causale.

---

## 6. Strategia di Test Automatizzati

### 6.1 Backend (`tests/backend/test_accounting_causals_sync.py` - Pytest)
1. Persistenza modello `AccountingCausal` e seed causali standard.
2. Collegamento `EventType` $\rightarrow$ `AccountingCausal` e `JournalEntry.causale_id`.
3. Emissione fattura: verifica generazione automatica `JournalEntry` e presenza evento `EMISSIONE_FATTURA` su Event Bus.
4. Incasso rata: verifica generazione automatica `JournalEntry` (Dare Banca, Avere Crediti) e presenza evento `INCASSO_RATA`.
5. Emissione nota di credito: verifica storno contabile e audit trail.
6. API CRUD `/api/accounting/causals` e modifica dinamica conti.

### 6.2 Frontend (`tests/frontend/Accounting.spec.js` - Vitest)
1. Verifica rendering scheda "Causali Contabili" e selettori conti.
