# Specifica Architetturale: Stampa Etichette Barcode Termiche (ZPL, Code 128, Formati Bancale 100x150 e Collo 50x30 con Dati Bio)

## 1. Obiettivo e Panoramica Funzionale

Implementare nel gestionale **`erp9lli`** il modulo di **Generazione e Stampa Etichette Barcode Termiche (`BarcodeLabelService`)** per l'identificazione di bancali e colli ortofrutticoli biologici lungo tutta la supply chain:
- **Formati Standard di Stampa Termica**:
  1. **Etichetta Bancale (Pallet SSCC - 100×150 mm / 4×6")**:
     - Testata aziendale: *"RETEBIO SOCIETÀ AGRICOLA"* e Dicitura Certificazione: *"Operatore Controllato IT-BIO-009 CCPB"*;
     - Articolo: Codice Prodotto, Descrizione (es. *"ARANCE TAROCCO BIO SICILIA"*), Calibro e Categoria;
     - Dati di Tracciabilità Biologica: Codice Lotto (es. `LOTTO: L-2026-TRC01`), Data Scadenza / Raccolta, Origine (*"Origine: Italia - Sicilia"*);
     - Dati Pesi e Imballo: Numero Colli (es. `Colli: 48`), Tara bancale (`25.0 kg`), Peso Netto (`480.0 kg`), Peso Lordo (`505.0 kg`);
     - Barcode Code 128 leggibile ad alta definizione con testo in chiaro;
  2. **Etichetta Collo / Cassetta (50×30 mm o 70×40 mm)**:
     - Etichetta compatta per singola cassa/confezione: Codice, Descrizione, Lotto Bio, Scadenza, Peso e Barcode Code 128.
- **Supporto Doppio Canale: Industriale (ZPL) e Web / Desktop (SVG / HTML)**:
  - **ZPL (Zebra Programming Language)**: comandi nativi ZPL (`^XA...^BC...^XZ`) a 203 DPI e 300 DPI per invio diretto via socket LAN (porta 9100) o spooler a stampanti industriali di magazzino (Zebra ZT411, ZD421, TSC, Intermec);
  - **Vettoriale SVG & HTML / CSS Print**: generazione barcode SVG in puro Python senza dipendenze binarie pesanti e anteprima grafica termica CSS `@page` per stampa diretta da browser su qualsiasi stampante termica USB (Zebra, Dymo, Brother, Xprinter, Epson).
- **Integrazione con i Flussi Operativi Esistenti**:
  - **Bollettazione DDT (`DeliveryNotes.vue`)**: pulsante rapido *"Etichette Bancale"* in tabella per stampare tutte le etichette delle merci in spedizione con i lotti bio già assegnati;
  - **Entrata Merci Fornitori (`Purchases.vue`)**: generazione etichette di carico con lotto fornitore per stoccaggio in celle frigo;
  - **Catalogo Prodotti (`ProductCatalog.vue`)**: stampa rapida etichette articolo/prezzo.
- **Tracciamento su Event Bus**:
  - Emissione evento su canale `AUDIT` con categoria `LOGISTICA` e azione `stampa_etichette_barcode`.

---

## 2. Servizio Generazione Etichette (`backend/services/barcode_label_service.py`)

### 2.1 Metodi del Servizio `BarcodeLabelService`
```python
class BarcodeLabelService:
    @staticmethod
    def generate_code128_svg(code: str, height: int = 50, bar_width: int = 2) -> str:
        """Genera SVG vettoriale puro del barcode Code 128 (Subset B)"""

    @staticmethod
    def generate_pallet_zpl(data: dict) -> str:
        """Genera comandi ZPL standard a 203 DPI per etichetta bancale 100x150 mm (800x1200 dots)"""

    @staticmethod
    def generate_collo_zpl(data: dict) -> str:
        """Genera comandi ZPL standard a 203 DPI per etichetta collo 50x30 mm (400x240 dots)"""

    @staticmethod
    def render_pallet_html(data: dict) -> str:
        """Genera frammento HTML con stile per rendering termico 100x150 mm"""

    @staticmethod
    def render_collo_html(data: dict) -> str:
        """Genera frammento HTML con stile per rendering termico 50x30 mm"""
```

### 2.2 Codifica Code 128 (Subset B) Nativa
Algoritmo integrato di codifica Code 128:
- Carattere di START B (`104`);
- Checksum ponderato modulo 103;
- Carattere di STOP (`106`);
- Generazione stringa SVG `<svg ...><rect .../></svg>` senza dipendenze da librerie grafiche esterne C (cairo, libpng, ecc.), garantendo massima portabilità in qualsiasi container Docker.

---

## 3. Specifiche API REST (`backend/app.py`)

Tutti gli endpoint richiedono `@require_auth()`:

- **`POST /api/labels/generate`**:
  - Genera etichetta on-demand per i parametri forniti:
    - Input: `label_type` (`pallet` | `collo`), `descrizione`, `codice_articolo`, `lotto`, `data_scadenza`, `colli`, `peso_netto`, `peso_lordo`, `tara`, `origine`, `ente_certificatore`.
    - Output: JSON contenente `zpl`, `svg_barcode`, `html_preview`, `barcode_value`.
- **`GET /api/delivery-notes/<int:id>/labels`**:
  - Genera il pacchetto etichette bancale per tutte le righe del DDT indicato, prelevando automaticamente lotti bio, colli, pesi e certificazione del cliente.
- **`GET /api/purchases/<int:id>/labels`**:
  - Genera le etichette di carico magazzino per le righe della bolla d'entrata merci indicata.

---

## 4. Specifiche Interfaccia Quasar (`frontend/src/components/`)

- **Componente Dialog Etichette Termiche (`frontend/src/components/BarcodeLabelsDialog.vue`)**:
  - Visualizzatore anteprima etichetta termica 100×150 mm con grafica realistica, badge biologico, griglia dati e barcode SVG;
  - Selettore formato etichetta: **Bancale (100×150 mm)** vs **Collo (50×30 mm)**;
  - Pulsante **"Stampa Termica (Browser)"**: apre la finestra di stampa con stili CSS `@media print` ottimizzati per etichette senza margini;
  - Pulsante **"Copia Codice ZPL"**: copia il codice Zebra per invio diretto via rete o software di etichettatura (ZebraDesigner, Bartender);
  - Pulsante **"Download ZPL (.txt)"**: scarica il file comandi grezzo.
- **Integrazione in `DeliveryNotes.vue`**:
  - Pulsante con icona `qr_code_2` e tooltip *"Stampa Etichette Bancale"* su ciascun DDT;
- **Integrazione in `ProductCatalog.vue`**:
  - Pulsante rapido *"Stampa Etichetta"* per ciascun prodotto del catalogo.

---

## 5. Strategia di Test Automatizzati

### 5.1 Backend (`tests/backend/test_barcode_labels.py` - Pytest)
1. Generazione corretta del codice SVG del barcode Code 128 (verifica start, stop, checksum e tag SVG).
2. Generazione ZPL per etichetta bancale (verifica comandi `^XA`, `^BC`, `^XZ`, presenza diciture bio e lotto).
3. Generazione ZPL per etichetta collo compatto.
4. Endpoint REST `/api/labels/generate`: test risposta completa (ZPL, SVG, HTML).
5. Endpoint REST `/api/delivery-notes/<id>/labels`: test generazione etichette da DDT reale.
6. Verifica emissione evento su Event Bus per tracciamento stampa.

### 5.2 Frontend (`tests/frontend/BarcodeLabels.spec.js` - Vitest)
1. Verifica rendering anteprima etichetta termica con barcode SVG e diciture biologiche.
2. Verifica presenza pulsanti Stampa e Copia ZPL.
