# Specifica Architetturale: Modulo Note di Credito (TD04) & Gestione Resi Merci

## 1. Obiettivo e Panoramica Funzionale

Implementare nel gestionale **`erp9lli`** il modulo di **Emissione e Gestione delle Note di Credito** (tipo documento SDI **`TD04`**) e dei **Resi Merci**, conforme alla normativa fiscale italiana e alle specifiche operative del **Gestionale ReteBio 2026** (Sezioni 2 e 5.7):
- **Tipizzazione Fiscale `TD04` & Serie Annuale Dedicata**:
  - Le Note di Credito costituiscono una serie di numerazione annuale autonoma:
    $$\text{Formato Numero} = \text{"NC-YYYY-XXXX"} \quad (\text{es. } \text{NC-2026-0001})$$
  - Collegamento biunivoco alla fattura di vendita d'origine (`invoice_origine_id`, `invoice_origine_numero`).
- **Mappatura Tracciato XML SDI FatturaPA (`<DatiFattureCollegate>`)**:
  - Nel tracciato XML `FPR12`, per i documenti di tipo `TD04` viene generato obbligatoriamente il blocco:
    ```xml
    <DatiGeneraliDocumento>
      <TipoDocumento>TD04</TipoDocumento>
      ...
    </DatiGeneraliDocumento>
    <DatiFattureCollegate>
      <IdDocumento>FT-2026-0001</IdDocumento>
      <Data>2026-10-31</Data>
    </DatiFattureCollegate>
    ```
- **Storno Fiscale Totale o Parziale**:
  - Possibilità di stornare l'intera fattura o specifiche righe/quantità (es. contestazione qualità, differenze peso, abbuoni commerciali).
  - Ricalcolo automatico del castelletto IVA proporzionale alle aliquote delle righe stornate.
- **Compensazione Finanziaria dello Scadenzario Rate**:
  - Se la fattura d'origine ha rate aperte nello scadenzario:
    - L'importo della nota di credito viene decurtato automaticamente a compensazione delle rate aperte della fattura d'origine, a partire dalla prima rata in scadenza.
    - Se l'importo della nota di credito pareggia il debito residuo, le rate passano a stato `'incassata'` e la fattura d'origine passa a stato `'saldata'`.
  - Se la fattura d'origine era già saldata:
    - La nota di credito genera una posizione creditoria a favore del cliente, utilizzabile in compensazione su pagamenti futuri.
- **Reintegro Opzionale a Magazzino (Reso Fisico Lotti Bio)**:
  - Se la nota di credito deriva da un reso fisico di merce biologica commercializzabile (`reintegro_magazzino = True`), il sistema ripristina la disponibilità a magazzino per la specifica combinazione `(product_id, lotto)`, riattivando il suggerimento FEFO per successive spedizioni.

---

## 2. Modello Dati Relazionale (`backend/models/invoice.py`)

Estensione del modello `Invoice`:
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `invoice_origine_id` | Integer | FK `invoice.id`, Nullable | ID della fattura stornata |
| `invoice_origine_numero` | String(30) | Nullable | Riferimento numero (es. `FT-2026-0001`) |
| `causale_storno` | Text | Nullable | Motivazione (reso merce, rettifica prezzo, abbuono) |
| `reintegro_magazzino` | Boolean | Not Null, default `False` | Se True, reintegra i lotti bio a magazzino |

Relazione auto-referenziale su `Invoice`:
```python
invoice_origine = db.relationship('Invoice', remote_side=[id], backref=db.backref('note_credito', lazy='dynamic'))
```

---

## 3. Specifiche API REST (`backend/app.py`)

Tutti gli endpoint richiedono `@require_auth()`:

- **`POST /api/invoices/<int:id>/credit-note`**:
  - Genera una Nota di Credito `NC-YYYY-XXXX` a storno della fattura `<id>`.
  - Payload di richiesta:
    ```json
    {
      "causale_storno": "Reso merce avariata durante trasporto",
      "reintegro_magazzino": false,
      "compensa_scadenzario": true,
      "items": [
        {
          "invoice_item_id": 1,
          "quantita_stornata": 20.0,
          "prezzo_unitario": 2.20,
          "aliquota_iva": 4
        }
      ]
    }
    ```
  - Risposta: `201 Created` con i dati completi della nota di credito emessa e lo stato aggiornato dello scadenzario della fattura d'origine.
- **`GET /api/invoices?tipo=TD04`**:
  - Filtro nella lista fatture per interrogare unicamente le Note di Credito.

---

## 4. Specifiche Tracciato XML SDI (`backend/services/sdi_service.py`)

- In `generate_sdi_xml`:
  - Se `invoice.tipo_documento == 'TD04'`:
    - Imposta `<TipoDocumento>TD04</TipoDocumento>`.
    - Genera il blocco `<DatiFattureCollegate>`:
      ```xml
      <DatiFattureCollegate>
        <IdDocumento>{invoice.invoice_origine_numero}</IdDocumento>
        <Data>{invoice.invoice_origine.data_documento.isoformat()}</Data>
      </DatiFattureCollegate>
      ```

---

## 5. Specifiche Interfaccia Utente Quasar (`frontend/src/components/Invoices.vue`)

1. **Tabella Documenti Fiscale**:
   - Badge distintivo per le note di credito:
     - Chip arancione/ambra: **`TD04 - NOTA DI CREDITO`**.
     - Visualizzazione del riferimento: *"Storno di FT-YYYY-XXXX"*.
   - Nella colonna *Azioni* delle fatture attive (`TD01`, `TD24`):
     - Pulsante rapido *"Emetti Nota di Credito"* (`icon="assignment_return"`).
2. **Dialog / Wizard Emissione Nota di Credito**:
   - Tabella delle righe della fattura con quantità originale e input per la quantità da stornare.
   - Campo motivazione/causale storno.
   - Toggle *"Compensa rate scadenzario esistenti"*.
   - Toggle *"Reintegra merci a magazzino (Lotti bio)"*.
   - Anteprima dell'importo totale a storno (imponibile + IVA).

---

## 6. Strategia di Test Automatizzati

### 6.1 Test Backend (`tests/backend/test_credit_notes.py` - Pytest)
1. `test_create_credit_note_partial_reversal`: verifica emissione `NC-YYYY-XXXX`, calcolo storno parziale e collegamento alla fattura d'origine.
2. `test_credit_note_installments_compensation`: verifica decurtazione o chiusura delle rate aperte nello scadenzario.
3. `test_credit_note_sdi_xml_with_dati_fatture_collegate`: verifica presenza di `<TipoDocumento>TD04</TipoDocumento>` e blocco `<DatiFattureCollegate>`.
4. `test_credit_note_stock_reintegration`: verifica reintegro delle giacenze a magazzino con ripristino lotto FEFO.

### 6.2 Test Frontend (`tests/frontend/Invoices.spec.js` - Vitest)
1. Verifica comparsa pulsante Nota di Credito e rendering chip `TD04`.
