# Specifica Architetturale: Architettura Modulare a Pacchetti e Modulo Ordini Clienti

## 1. Obiettivo e Visione Architetturale

Questo documento definisce due componenti strettamente correlati per l'evoluzione enterprise di **`erp9lli`**:
1. **Framework di Modularità e Feature Flags (`ENABLED_MODULES`)**:
   - Capacità di attivare, disattivare o commercializzare singole combinazioni di pacchetti (es. solo *Ordini e Fatture*, solo *Contabilità*, o *Ciclo Completo*).
   - Registrazione condizionale lato backend tramite Blueprint/Feature Flags.
   - Endpoint informativo `GET /api/modules` per comunicare al frontend l'elenco dei moduli concessi in licenza.
   - Adattamento dinamico lato frontend Vue 3: la Sidebar Quasar e le rotte mostrano e consentono l'accesso unicamente alle funzionalità abilitate.
2. **Modulo Supply Chain 1: Ciclo Ordini Clienti & Evasione in DDT**:
   - Porting della gestione ordini di ReteBio (`T_Ordini`, `T_RigheOrd`):
     - Numerazione sequenziale annuale (`ORD-YYYY-XXXX`).
     - Gestione righe a sequenze intercalate (passi di 5: 5, 10, 15...).
     - Tracciamento delle quantità ordinate, consegnate e del **Residuo da consegnare**.
     - Wizard di evasione diretta in Bolle di Consegna (DDT), con aggiornamento automatico dello stato dell'ordine ad `'in_preparazione'` o `'chiuso'`.

---

## 2. Framework di Modularità e Parametrizzazione Installazione

### 2.1 Configurazione `.env`
Variabile di configurazione installazione:
```bash
# Esempio Full ERP (tutti i moduli attivi):
ENABLED_MODULES=anagrafiche,orders,delivery_notes,invoicing,accounting

# Esempio Installazione Solo Commerciale (senza contabilità e senza DDT):
# ENABLED_MODULES=anagrafiche,orders,invoicing
```
Valore di default: `'all'` (tutti i moduli attivi).

### 2.2 Endpoint Backend: `GET /api/modules`
Restituisce il dizionario booleano dei moduli attivi per l'istanza:
```json
{
  "anagrafiche": true,
  "orders": true,
  "delivery_notes": true,
  "invoicing": true,
  "accounting": true
}
```

### 2.3 Registry Dinamico Frontend (`App.vue` & `router.js`)
- All'avvio dell'applicazione (`App.vue`), viene interrogato `/api/modules`.
- La Sidebar laterale Quasar (`q-drawer`) renderizza i gruppi e le voci di menu solo se il modulo corrispondente è attivo:
  - `orders` -> mostra "Ordini Clienti" (`/orders`)
  - `delivery_notes` -> mostra "Bolle (DDT)" (`/delivery-notes`)
  - `invoicing` -> mostra "Fatture & Scadenzario" (`/invoices`)
  - `accounting` -> mostra "Contabilità & Bilancio" (`/accounting`)
  - `anagrafiche` -> mostra "Soggetti" e "Articoli"
- Se un utente naviga manualmente verso una rotta disabilitata, la Navigation Guard di `router.js` reindirizza a `/dashboard`.

---

## 3. Modello Dati del Modulo Ordini (`backend/models/`)

### 3.1 Tabella `customer_order` (`backend/models/customer_order.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco ordine |
| `numero` | Integer | Not Null | Progressivo annuale (1, 2, 3...) |
| `anno` | Integer | Not Null | Anno solare (es. 2026) |
| `numero_completo` | String(30) | Not Null, Unique, Index | Formato stringa (`ORD-YYYY-XXXX`) |
| `data_ordine` | Date | Not Null, default `today` | Data emissione/ricezione ordine |
| `data_richiesta` | Date | Nullable | Data di consegna richiesta dal cliente |
| `data_confermata`| Date | Nullable | Data di consegna confermata dall'azienda |
| `cliente_id` | Integer | FK `partner.id`, Not Null | Cliente intestatario dell'ordine |
| `stato` | String(20) | Not Null, default `'aperto'` | `'aperto'`, `'in_preparazione'`, `'chiuso'` |
| `totale_imponibile`| Float | Not Null, default `0.0` | Totale imponibile dell'ordine (€) |
| `note` | Text | Nullable | Note interne o istruzioni di consegna |

### 3.2 Tabella `order_item` (`backend/models/order_item.py`)
| Campo | Tipo | Vincoli | Descrizione |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, auto-increment | Identificativo univoco riga |
| `order_id` | Integer | FK `customer_order.id`, Not Null | Riferimento testata ordine (cascade delete) |
| `product_id` | Integer | FK `product.id`, Not Null | Articolo ordinato |
| `sequenza` | Integer | Not Null, default `5` | Numerazione a passi di 5 (5, 10, 15...) |
| `descrizione` | String(200) | Not Null | Descrizione articolo |
| `unita_misura` | String(10) | Not Null, default `'KG'` | Unità di misura |
| `colli_ordinati` | Integer | Not Null, default `1` | Numero colli richiesti |
| `quantita_ordinata`| Float | Not Null | Quantità ordinata |
| `colli_consegnati`| Integer | Not Null, default `0` | Numero colli già evasi |
| `quantita_consegnata`| Float| Not Null, default `0.0` | Quantità già evasa su DDT |
| `prezzo_unitario` | Float | Not Null, default `0.0` | Prezzo concordato di vendita |
| `aliquota_iva` | Integer | Not Null, default `4` | Aliquota IVA applicata |
| `lotto` | String(50) | Nullable | Lotto assegnato (se noto in pre-ordine) |
| `stato` | String(20) | Not Null, default `'aperto'` | `'aperto'`, `'chiuso'` |

**Calcolo Residuo**:
$$\text{quantita\_residua} = \max(0.0, \text{quantita\_ordinata} - \text{quantita\_consegnata})$$
Una riga d'ordine passa automaticamente a `'chiuso'` quando $\text{quantita\_consegnata} \ge \text{quantita\_ordinata}$.

---

## 4. Specifiche API REST (`backend/app.py` o Blueprint)

Tutti gli endpoint richiedono `@require_auth()`:

- **`GET /api/modules`**:
  - Restituisce la mappa dei moduli abilitati.
- **`GET /api/orders`**:
  - Parametri filtro: `stato` (`aperto`, `in_preparazione`, `chiuso`, `tutti`), `cliente_id`, `anno`, `search`.
- **`GET /api/orders/<id>`**:
  - Dettaglio completo testata e righe con colli/quantità ordinate, consegnate e residuo calcolato.
- **`POST /api/orders`**:
  - Creazione nuovo ordine con righe a numerazione sequenziale a passi di 5 (5, 10, 15...).
  - Generazione progressivo `ORD-YYYY-XXXX`.
- **`PUT /api/orders/<id>`**:
  - Modifica ordine (consentita se non ancora interamente chiuso).
- **`POST /api/orders/<id>/fulfill-to-ddt`**:
  - Procedura di **Evasione Ordine in DDT**:
    - Riceve le righe e le quantità da evadere (default: intero residuo disponibile).
    - Genera una nuova Bolla (DDT) per il cliente contenente le righe evase.
    - Aggiorna contestualmente `quantita_consegnata` sulle righe dell'ordine.
    - Se tutte le righe sono soddisfatte, imposta lo stato dell'ordine a `'chiuso'`, altrimenti `'in_preparazione'`.
    - Risposta `201 Created` con il DDT generato e l'ordine aggiornato.

---

## 5. Specifiche Interfaccia Utente Quasar (`frontend/src/`)

### 5.1 Componente `Orders.vue`
- Tabella `<q-table>` ordini clienti:
  - Numero Ordine (`ORD-2026-0001`), Data Ordine, Data Consegna, Cliente, Imponibile, Avanzamento Evasione (% completamento), Stato.
  - Badge colorati di stato: Arancione (*Aperto*), Blu (*In preparazione*), Verde (*Chiuso*).
  - Azione *"Evadi in DDT"*: apre il wizard modale di evasione con selezione delle quantità residue da caricare sulla bolla.
- **Dialog Nuovo Ordine**:
  - Selezione Cliente, date, e tabella righe dinamiche con colli, quantità, prezzo e sequenza progressiva.

### 5.2 Navigazione & Dynamic Registry
- Nuova rotta `/orders` registrata nel router.
- La sidebar Quasar mostra *"Ordini Clienti"* sotto il gruppo *"Ciclo Attivo (Vendite)"* se il modulo `orders` è abilitato.

---

## 6. Strategia di Test Automatizzati

### 6.1 Test Backend (`tests/backend/test_orders_and_modules.py`)
1. `test_get_modules_endpoint`: verifica risposta di `GET /api/modules` in base a `ENABLED_MODULES`.
2. `test_create_order_with_step5_sequences`: verifica creazione ordine con sequenze 5, 10, 15... e numerazione `ORD-YYYY-XXXX`.
3. `test_order_partial_fulfillment_to_ddt`: evasione parziale dell'ordine, verifica creazione del DDT e stato ordine `'in_preparazione'` con residuo corretto.
4. `test_order_full_fulfillment_closes_order`: evasione a saldo del residuo, verifica chiusura automatica ordine (`stato = 'chiuso'`).

### 6.2 Test Frontend (`tests/frontend/Orders.spec.js`)
1. Verifica rendering tabella ordini, barra di avanzamento e pulsante evasione DDT.

---

## 7. Piano di Migrazione Database
- Esecuzione migrazione Alembic nel container Docker:
  `flask db migrate -m "add customer order models"`
  `flask db upgrade`
