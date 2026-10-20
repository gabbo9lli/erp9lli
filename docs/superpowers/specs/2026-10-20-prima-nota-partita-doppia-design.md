# Specifica Architetturale: Modulo Prima Nota, Partita Doppia e Documenti Contabili per erp9lli

## 1. Obiettivo e Panoramica Funzionale

Introdurre nel gestionale **`erp9lli`** il modulo di **Contabilità Generale a Partita Doppia, Prima Nota e Reporting Civilistico**, colmando il gap del vecchio programma Access di ReteBio (che delegava interamente all'esterno la contabilità generale ordinaria):
- **Piano dei Conti Gerarchico (`Account`)**: codifica standard a 4 mastri fondamentali (*Attivo*, *Passivo*, *Costi*, *Ricavi*) con conti e sottoconti preconfigurati per la gestione aziendale.
- **Scritture di Prima Nota a Pareggio Bilanciato (`JournalEntry` & `JournalItem`)**:
  - Imposizione transazionale del principio cardinale della Partita Doppia:
    $$\sum \text{Dare (Debit)} = \sum \text{Avere (Credit)}$$
  - Rifiuto con errore bloccante `400 Bad Request` di qualsiasi scrittura contabile con sbilancio.
  - Numerazione progressiva annuale univoca del Libro Giornale (`PN-YYYY-XXXX`).
  - Associazione facoltativa con l'anagrafica commerciale (`Partner`) per la gestione dei partitari clienti e fornitori.
- **Reporting e Documenti Contabili con Motore di Export Duale (Web Viewer + CSV)**:
  - **Libro Giornale**: registro cronologico di tutte le registrazioni con progressivi dare/avere e quadratura generale.
  - **Schede Mastro (Libro Mastro)**: estratto conto dare/avere per singolo conto o per partitario partner con calcolo del **Saldo Progressivo**.
  - **Bilancio di Verifica (Trial Balance)**: prospetto sintetico di tutti i conti movimentati con totale dare, totale avere e saldo netto a pareggio bilancio.
  - Tutti i report sono consultabili a video su Quasar ed esportabili direttamente in formato **CSV/Excel** standard per lo studio del commercialista.

---

## 2. Modello Dati Relazionale (`backend/models.py`)

### 2.1 Tabella `account` (Piano dei Conti)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `codice` | String(20) | Not Null, Unique, Index | Codice conto (es. `1001`, `1101`, `2001`, `4101`) |
| `nome` | String(100) | Not Null | Denominazione del conto contabile |
| `tipo` | String(20) | Not Null | Tipologia CEE: `'attivo'`, `'passivo'`, `'costi'`, `'ricavi'` |
| `attivo` | Boolean | Not Null, default `True` | Abilitazione del conto |

### 2.2 Tabella `journal_entry` (Testata Registrazione di Prima Nota)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `numero` | Integer | Not Null | Progressivo annuale Libro Giornale (1, 2, ...) |
| `anno` | Integer | Not Null | Anno solare di competenza (es. 2026) |
| `numero_completo` | String(30) | Not Null, Unique, Index | Formato stringa (`PN-YYYY-XXXX`) |
| `data_registrazione`| Date | Not Null | Data di registrazione contabile |
| `data_competenza` | Date | Not Null | Data economica di competenza |
| `causale` | String(200) | Not Null | Descrizione dell'operazione contabile |
| `totale_dare` | Float | Not Null, default `0.0` | Somma dei valori Dare della scrittura |
| `totale_avere` | Float | Not Null, default `0.0` | Somma dei valori Avere della scrittura |
| `stato` | String(20) | Not Null, default `'confermata'` | `'bozza'`, `'confermata'` |
| `note` | Text | Nullable | Eventuali annotazioni contabili |

### 2.3 Tabella `journal_item` (Righe Contabili Dare / Avere)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco di riga |
| `journal_entry_id` | Integer | FK `journal_entry.id`, Not Null | Riferimento testata (cascade delete) |
| `account_id` | Integer | FK `account.id`, Not Null | Conto di mastro imputato |
| `partner_id` | Integer | FK `partner.id`, Nullable | Partner associato per partitari |
| `dare` | Float | Not Null, default `0.0` | Importo iscritto in Dare (addebito) |
| `avere` | Float | Not Null, default `0.0` | Importo iscritto in Avere (accredito) |
| `descrizione_riga`| String(200) | Nullable | Descrizione specifica della riga |

---

## 3. Parametrizzazione e Setup del Piano dei Conti Base

Uno script dedicato di seed (`backend/seed_accounting.py`) inizializza il Piano dei Conti standard italiano all'avvio:
- **Attivo**:
  - `1001`: Cassa Contanti
  - `1002`: Banca c/c Principale
  - `1101`: Crediti v/Clienti
  - `2202`: Erario c/IVA a Credito
- **Passivo**:
  - `2001`: Debiti v/Fornitori
  - `2201`: Erario c/IVA a Debito
  - `3001`: Capitale Sociale e Riserve
- **Costi**:
  - `5101`: Costi Merci Conto Acquisti
  - `5201`: Spese di Trasporto e Logistica
  - `5301`: Spese e Commissioni Bancarie
- **Ricavi**:
  - `4101`: Ricavi Vendite Prodotti Biologici
  - `4201`: Ricavi Prestazioni e Cauzioni

---

## 4. Specifiche API REST (`backend/app.py`)

Tutte le rotte contabili sono protette con `@require_auth()`:

### 4.1 Gestione Conti e Prima Nota
- `GET /api/accounting/accounts`: restituisce il Piano dei Conti ordinato per codice.
- `POST /api/accounting/accounts`: inserimento nuovo conto (richiede ruolo `Admin`).
- `GET /api/accounting/entries`: elenco scritture di prima nota (con filtri per data inizio/fine, ricerca causale).
- `GET /api/accounting/entries/<id>`: dettaglio scrittura con tutte le righe contabili.
- `POST /api/accounting/entries`: creazione nuova registrazione di Prima Nota.
  - **Validazione Vincolo di Pareggio**:
    ```python
    totale_dare = round(sum(item['dare'] for item in items), 2)
    totale_avere = round(sum(item['avere'] for item in items), 2)
    if abs(totale_dare - totale_avere) > 0.001:
        return jsonify({"error": f"Scrittura sbilanciata! Dare (€ {totale_dare}) != Avere (€ {totale_avere})"}), 400
    ```
  - Generazione automatica progressivo Libro Giornale `numero_completo = f"PN-{anno}-{numero:04d}"`.

### 4.2 Motore Documenti Contabili ed Export
Ciascun endpoint supporta il parametro `?format=csv` (restituisce file scaricabile con header `text/csv`) o `?format=json` (default per il Web Viewer Quasar):
- **`GET /api/accounting/reports/libro-giornale`**:
  - Parametri: `anno`, `data_inizio`, `data_fine`.
  - Estrae cronologicamente tutte le scritture confermate, esponendo per ogni riga: Data, Numero PN, Causale, Codice Conto, Nome Conto, Dare, Avere e progressivo quadratura cumulativo.
- **`GET /api/accounting/reports/mastro`**:
  - Parametri: `account_id` (obbligatorio) e opzionalmente `partner_id`, `data_inizio`, `data_fine`.
  - Estrae i movimenti del singolo conto, calcolando riga per riga il **Saldo Progressivo** (addebito/accredito).
- **`GET /api/accounting/reports/bilancio-verifica`**:
  - Parametri: `anno` (default anno corrente).
  - Raggruppa tutti i conti del piano dei conti e calcola per ciascuno: Totale Dare, Totale Avere e Saldo Netto, con riga finale di quadratura generale a pareggio tra Attivo, Passivo, Costi e Ricavi.

---

## 5. Specifiche Interfaccia Utente Quasar (`frontend/src/`)

### 5.1 Componente `Accounting.vue`
Console contabile strutturata a schede:
1. **Scheda "Prima Nota"**:
   - Tabella delle scritture registrate.
   - Pulsante *"Nuova Registrazione"* che apre il form modale a righe dinamiche con **indicatore visivo di sbilancio** in tempo reale (badge verde *BILANCIATO* se Dare == Avere, rosso con differenza in € se sbilanciato; pulsante Salva abilitato solo a pareggio).
2. **Scheda "Libro Giornale"**:
   - Tabella visualizzatrice delle scritture cronologiche.
   - Pulsante *"Esporta CSV Libro Giornale"* con download diretto.
3. **Scheda "Schede Mastro"**:
   - Selettore del conto (es. *1002 - Banca c/c*, *1101 - Crediti v/Clienti*).
   - Tabella estratto conto con colonna Saldo Progressivo.
   - Pulsante *"Esporta CSV Mastro"*.
4. **Scheda "Bilancio di Verifica"**:
   - Tabella sinottica dei conti con totali Dare, Avere e Saldo.
   - Box di quadratura finale a fondo pagina.
   - Pulsante *"Esporta CSV Bilancio"*.
5. **Scheda "Piano dei Conti"**:
   - Consultazione e aggiunta conti.

### 5.2 Navigazione Principale (`App.vue` & `router.js`)
- Nuova rotta protetta `/accounting`.
- Aggiunta della voce **"Contabilità"** nella navbar superiore.

---

## 6. Strategia di Test Automatizzati

### 6.1 Test Backend (`tests/backend/test_accounting.py` - Pytest)
1. `test_seed_chart_of_accounts`: verifica inizializzazione conti standard.
2. `test_unbalanced_journal_entry_rejected`: scrittura con Dare != Avere respinta con errore 400.
3. `test_balanced_journal_entry_creation`: scrittura a pareggio accettata con assegnazione automatica del numero `PN-YYYY-XXXX`.
4. `test_libro_giornale_report_json_and_csv`: verifica calcolo progressivi sia in JSON che in export CSV.
5. `test_mastro_report_running_balance`: verifica calcolo del saldo progressivo.
6. `test_bilancio_di_verifica_balance`: verifica che il bilancio di verifica quadri e pareggi tra totale dare e avere.

### 6.2 Test Frontend (`tests/frontend/Accounting.spec.js` - Vitest)
1. Verifica rendering schede contabili, tabella scritture e presenza pulsanti di export CSV.
2. Verifica dell'indicatore di bilanciamento nel form di prima nota.

---

## 7. Piano di Migrazione Database
- Esecuzione migrazione Alembic nel container Docker:
  `flask db migrate -m "add accounting models"`
  `flask db upgrade`
- Esecuzione dello script di seed dei conti contabili:
  `python seed_accounting.py`
