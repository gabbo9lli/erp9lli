# Specifica Architetturale: Modulo Fatturazione Elettronica SDI (Tracciato XML FPR12 / FatturaPA v1.2.2)

## 1. Obiettivo e Panoramica Funzionale

Implementare nel gestionale **`erp9lli`** il modulo di **Generazione ed Esportazione della Fattura Elettronica SDI**, conforme alle specifiche tecniche ufficiali dell'Agenzia delle Entrate (**FatturaPA v1.2.2**, formato **`FPR12`** per fatture ordinarie tra privati B2B e B2C) e alle regole operative del **Gestionale ReteBio 2026** (Sezione 5.7):
- **Tracciato XML Conforme al Namespace SDI**:
  - Namespace ufficiale: `xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"`
  - Codifica del documento in `UTF-8` con intestazione XML e validazione strutturale dei nodi `<FatturaElettronicaHeader>` e `<FatturaElettronicaBody>`.
  - Denominazione del file secondo le regole di trasmissione dell'Agenzia delle Entrate:
    $$\text{Nome File} = \text{"IT"} + \text{CodiceFiscaleCedente (11 o 16 caratteri)} + \text{"\_"} + \text{ProgressivoUnivoco (5 alfanumerici)} + \text{".xml"}$$
- **Mappatura Fiscale Intelligente dei Codici e delle Nature IVA**:
  - `TipoDocumento`: `TD24` per fatture differite da DDT, `TD01` per fatture immediate/accompagnatorie, `TD04` per note di credito.
  - `EsigibilitaIVA`: `'I'` (immediata), `'D'` (differita), `'S'` (split payment per enti pubblici).
  - Determinazione automatica della casella `<Natura>` in presenza di `AliquotaIVA == 0%`:
    - Se fattura per mancata restituzione pallet (L. 182/2025): **`N6.7`** (*Inversione contabile - cessione di rottami e altri materiali di recupero / imballaggi usati ex art. 74 c. 7/8*).
    - Se cliente con nazione comunitaria estera (`nazione != 'IT'` e nazione UE): **`N3.2`** (*Cessioni intracomunitarie non imponibili*).
    - Se cliente extra-UE: **`N3.1`** (*Esportazioni non imponibili*).
    - Altre operazioni esenti: **`N4`**.
- **Gestione del Blocco `<DatiDDT>` per Fatture Differite (TD24)**:
  - Per ciascun DDT richiamato nelle righe della fattura, genera i nodi `<DatiDDT>` indicando `<NumeroDDT>`, `<DataDDT>` e l'elenco dei numeri di linea collegati, adempimento obbligatorio per la detraibilità IVA delle fatture differite.
- **Ripartizione Finanziaria in `<DatiPagamento>`**:
  - Mappatura dello scadenzario rate (`InvoiceInstallment`):
    - `<CondizioniPagamento>`: `TP01` se rate multiple, `TP02` se pagamento completo in unica soluzione.
    - `<ModalitaPagamento>`: `MP05` (Bonifico Bancario), `MP12` (RI.BA), `MP01` (Contanti / Rimessa Diretta).
    - Data di scadenza, importo esatto della rata e coordinate bancarie con codice `<IBAN>`.
- **Validatore Preventivo di Conformità SDI**:
  - Controllo formale pre-invio: verifica presenza di Partita IVA o Codice Fiscale valido del cliente, CAP a 5 cifre, Codice Destinatario (7 caratteri alfanumerici) o `0000000` con valorizzazione dell'indirizzo PEC, e quadratura algebrica al centesimo di euro:
    $$\sum \text{Imponibili} + \sum \text{Imposte} = \text{Totale Fattura} = \sum \text{Rate Scadenzario}$$

---

## 2. Modello Dati e Architettura dei Moduli

I modelli dati relazionali sono già presenti in `backend/models/`:
- `Invoice`: testata fattura (`numero_completo`, `anno`, `tipo_documento`, `data_documento`, `totale_imponibile`, `totale_imposta`, `totale_fattura`, `castelletto_iva`, `esigibilita_iva`, `note`).
- `Partner`: anagrafica cliente e cedente (`ragione_sociale`, `partita_iva`, `codice_fiscale`, `codice_sdi`, `pec`, `indirizzo`, `cap`, `citta`, `provincia`, `nazione`, `iban`).
- `InvoiceItem`: righe merce (`descrizione`, `unita_misura`, `quantita`, `prezzo_unitario`, `aliquota_iva`, `imponibile_riga`, `delivery_note_id`).
- `InvoiceInstallment`: rate (`numero_rata`, `totale_rate`, `data_scadenza`, `importo`, `stato`).

### Modulo Generatore XML (`backend/services/sdi_service.py`)
Funzione principale:
```python
def generate_sdi_xml(invoice: Invoice, cedente: dict = None) -> tuple[str, str]:
    """Genera la stringa XML conforme a FatturaPA v1.2.2 (FPR12) e il nome file ufficiale SDI.
    Restituisce (xml_string, filename).
    """
```
Funzione di validazione preventiva:
```python
def validate_sdi_invoice(invoice: Invoice) -> dict:
    """Valida formalmente la fattura restituendo un dizionario con stato, errori bloccanti e avvisi."""
```

---

## 3. Specifiche API REST (`backend/app.py`)

Tutti gli endpoint richiedono `@require_auth()`:

- **`GET /api/invoices/<int:id>/xml`**:
  - Genera l'XML conforme a FatturaPA v1.2.2.
  - Header HTTP restituiti:
    - `Content-Type: application/xml; charset=utf-8`
    - `Content-Disposition: attachment; filename="IT01234567890_XXXXX.xml"`
  - Se mancano dati fiscali critici, restituisce `HTTP 400 Bad Request` con l'elenco degli errori di validazione formale.
- **`GET /api/invoices/<int:id>/sdi-validate`**:
  - Restituisce lo stato di conformità per lo SDI senza generare il download:
    ```json
    {
      "valido": true,
      "errori": [],
      "avvisi": [],
      "codice_destinatario": "M5UXCR1",
      "tipo_documento": "TD24",
      "totale_documento": 1250.80,
      "nome_file_previsto": "IT01234567890_00001.xml"
    }
    ```

---

## 4. Specifiche Interfaccia Utente Quasar (`frontend/src/components/Invoices.vue`)

1. **Azione Rapida nella Tabella Fatture**:
   - Nella colonna *Azioni* di ogni riga fattura:
     - Pulsante **"XML"** con icona `code` o `download` e tooltip *"Scarica XML Fattura Elettronica (SDI)"*.
2. **Dialog Dettaglio Fattura**:
   - Badge di conformità SDI:
     - Verde: *"Pronto per lo SDI"*
     - Arancione con icona `warning`: elenco degli avvisi (es. *"Codice SDI generico 0000000 senza PEC registrata"*).
   - Pulsante dedicato in calce al dialog: *"Esporta Tracciato SDI (XML)"*.

---

## 5. Strategia di Test Automatizzati

### 5.1 Test Backend (`tests/backend/test_sdi_export.py` - Pytest)
1. `test_generate_sdi_xml_differita_td24_with_ddt_references`: verifica presenza nodi `<FatturaElettronicaHeader>`, `<DatiGeneraliDocumento>`, `<DatiDDT>` con numero e data bolla, e `<DatiBeniServizi>`.
2. `test_generate_sdi_xml_reverse_charge_nature_n6`: verifica che fattura pallet al 0% IVA contenga `<Natura>N6.7</Natura>`.
3. `test_generate_sdi_xml_installments_tp01_tp02`: verifica presenza rate scadenzario in `<DatiPagamento>`.
4. `test_sdi_validation_endpoint`: verifica controlli bloccanti su codice SDI/PEC e P.IVA.

### 5.2 Test Frontend (`tests/frontend/Invoices.spec.js` - Vitest)
1. Verifica comparsa pulsante download XML SDI nella tabella e invocazione download.
