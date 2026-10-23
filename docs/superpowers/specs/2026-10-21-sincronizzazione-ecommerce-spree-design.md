# Specifica Architetturale: Connettore & Sincronizzazione E-Commerce (Spree Commerce API / Webhook Shop)

## 1. Obiettivo e Panoramica Funzionale

Implementare nel gestionale **`erp9lli`** il modulo di **Integrazione e Sincronizzazione E-Commerce (`EcommerceService`)**, consentendo la ricezione automatica degli ordini dallo shop online (standard Spree Commerce / webhook JSON) e l'allineamento in tempo reale delle giacenze di magazzino residue:
- **Ricezione Idempotente Ordini Online (`POST /api/ecommerce/webhook/orders`)**:
  - Endpoint webhook protetto da autenticazione o API Key segreta (`X-Ecommerce-Secret`);
  - Ricezione payload ordine Spree Commerce contenente riferimento esterno (`number`), dati acquirente, indirizzo di spedizione e righe articoli (`line_items` con `sku`, `quantity`, `price`);
  - Auto-provisioning o lookup del cliente (`Partner`) a database;
  - Creazione automatica del `CustomerOrder` con sequenza righe a step 5 (`5, 10, 15...`) e stato `confermato`, pronto per l'evasione a DDT;
  - **Idempotenza garantita**: se un ordine con lo stesso `external_reference` è già stato importato, il sistema non lo duplica e restituisce HTTP 200 con l'ordine esistente;
- **Sincronizzazione Giacenze e Prezzi Catalogo (`GET /api/ecommerce/sync/stock`)**:
  - Calcolo in tempo reale delle disponibilità effettive di magazzino (carichi fornitore meno scarichi DDT e vendite al banco POS);
  - Restituzione formato JSON standard Spree/Shop per l'aggiornamento automatico dello shop online;
- **Tracciamento e Registro Sincronizzazioni (`EcommerceSyncLog`)**:
  - Modello relazionale per l'audit trail di tutti i webhook ricevuti e delle sincronizzazioni con payload, timestamp ed esito (`success`, `warning`, `error`);
  - Emissione automatica evento su Event Bus con canale `WEBHOOK` e categoria `VENDITE` (`ordine_ecommerce_ricevuto`).
- **Interfaccia Quasar (`frontend/src/components/Orders.vue`)**:
  - Badge identificativo `ECOMMERCE` con codice ordine esterno;
  - Scheda/Dialog per visualizzare lo storico delle sincronizzazioni e scaricare il feed giacenze per lo shop.

---

## 2. Modello Dati Relazionale (`backend/models/`)

### 2.1 Tabella `ecommerce_sync_log` (`backend/models/ecommerce_sync_log.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco |
| `tipo_operazione` | String(30) | Not Null | `'import_order'`, `'sync_stock'`, `'export_catalog'` |
| `external_order_id`| String(50) | Nullable, Index | ID ordine su Spree Commerce |
| `customer_order_id`| Integer | FK `customer_order.id`, Nullable | Ordine gestionale collegato |
| `stato` | String(20) | Not Null, default `'success'` | `'success'`, `'warning'`, `'error'` |
| `payload_ricevuto` | JSON | Nullable | Payload JSON ricevuto nel webhook |
| `dettaglio_risposta`| Text | Nullable | Note o messaggio di esito |
| `timestamp` | DateTime | Not Null, default utcnow | Timestamp ricezione/sincronizzazione |

### 2.2 Estensione di `customer_order` (`backend/models/customer_order.py`)
| Campo Aggiunto | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `external_reference`| String(100) | Nullable, Index | Codice ordine esterno (es. `SPREE-R123456789`) |
| `canale_vendita` | String(30) | Not Null, default `'diretto'` | `'diretto'`, `'ecommerce'`, `'bancom'` |

---

## 3. Specifiche del Servizio E-Commerce (`backend/services/ecommerce_service.py`)

```python
class EcommerceService:
    @staticmethod
    def process_incoming_order(payload: dict) -> tuple[CustomerOrder, bool]:
        """
        Importa un ordine da Spree Commerce / Webhook JSON.
        Restituisce (ordine, is_new: bool).
        Se già presente (stesso external_reference), restituisce quello esistente con is_new=False.
        """

    @staticmethod
    def get_stock_sync_feed() -> list[dict]:
        """
        Calcola giacenze residue reali per ogni SKU attivo e restituisce lista:
        [{"sku": "BIO-ARAN-TRC", "name": "Arance...", "price": 2.20, "stock": 480.0, "in_stock": True}]
        """
```

---

## 4. Specifiche API REST (`backend/app.py`)

- **`POST /api/ecommerce/webhook/orders`**:
  - Endpoint per ricezione ordini;
  - Autenticazione: header `X-Forwarded-*` oppure `X-Ecommerce-Secret` matching `os.getenv("ECOMMERCE_WEBHOOK_SECRET", "spree-secret-token")`;
  - Risposta `201 Created` per nuovi ordini, `200 OK` per ordini già importati (idempotenza);
- **`GET /api/ecommerce/sync/stock`**:
  - Restituisce feed JSON aggiornato delle giacenze per lo shop online;
- **`GET /api/ecommerce/logs`**:
  - Elenco storico delle sincronizzazioni e webhook ricevuti;

---

## 5. Specifiche Interfaccia Quasar (`frontend/src/components/Orders.vue`)

- Colonna Canale nella tabella ordini: badge `ECOMMERCE` verde con riferimento ordine esterno Spree;
- Dialog per visualizzare i log delle sincronizzazioni e testare un webhook d'esempio.

---

## 6. Strategia di Test Automatizzati

### 6.1 Backend (`tests/backend/test_ecommerce_sync.py` - Pytest)
1. Persistenza modello `EcommerceSyncLog` e campi `external_reference`, `canale_vendita` su `CustomerOrder`.
2. Importazione ordine Spree Commerce con auto-provisioning cliente, sequenze step 5 e calcolo totali.
3. Idempotenza: secondo invio dello stesso ordine restituisce HTTP 200 senza duplicare righe o ordini.
4. Calcolo feed giacenze `/api/ecommerce/sync/stock`.
5. Rifiuto webhook non autorizzato (secret errato).
6. Emissione evento su Event Bus per ordini e-commerce.

### 6.2 Frontend (`tests/frontend/Orders.spec.js` - Vitest)
1. Visualizzazione badge canale `ECOMMERCE` e riferimento esterno.
