# Legacy Access ERP Migration & System Initialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a dual-mode migration and system initialization engine that extracts legacy Access data (`GestionaleReteBio2026.accdb` and historical annual databases), supports safe reproducible wipe-and-load resets, and performs idempotent incremental imports with real-time WebSocket progress.

**Architecture:** Conforms to Clean Architecture: a dedicated ORM tracking table (`LegacyMigrationSync`), domain extraction and normalization engine in `LegacyMigrationService`, thin FastAPI router in `/api/migration`, and a Quasar/Vue 3 UI dashboard (`LegacyMigration.vue`) connected to WebSockets.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, `mdb-tools` (`mdb-export`), Vue 3, Quasar Framework, Vitest, Pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-legacy-migration-design.md`

## Global Constraints

- Never drop or delete records from the `users` table during system reset; the logged-in administrator must retain credentials and session.
- Always require the exact authorization token `"RESET_ERP9LLI"` to execute the database wipe.
- Maintain idempotency across multiple runs: duplicate runs on the same Access file must not duplicate partners, products, invoices, or stock lots.
- Git commits must always be signed with key `8B91C26B23264F4407CD41343FD13DC88C48D7E0` and author `gabbo <gabbo9lli@gmail.com>`.

## Review Focus

- Unsanitized strings with single/double quotes or accented characters from Access must not cause SQL or parser syntax errors.
- Documents with missing dates or malformed date formats (`MM/DD/YY` vs `DD/MM/YY`) must fallback safely to parsed dates or today's date without crashing.
- Accidental wipe attempt with invalid or missing confirmation token must be rejected with HTTP 400.
- Products with existing codes or Partners with matching business names must update/reuse records rather than creating duplicated rows.
- WebSocket broadcast must be delivered at every stage of the migration pipeline.

---

### Task 1: Modello ORM `LegacyMigrationSync` e Migrazione Alembic

**Files:**
- Create: `backend/models/legacy_migration_sync.py`
- Modify: `backend/models/__init__.py`
- Create: `backend/migrations/versions/<hash>_add_legacy_migration_sync.py`
- Test: `tests/backend/test_legacy_migration.py`

**Interfaces:**
- Produces: `LegacyMigrationSync` model in `backend/models/` with fields `id`, `source_file`, `entity_type`, `legacy_id`, `target_id`, `anno`, `created_at`, `updated_at`.

- [ ] **Step 1: Scrivere il test per la persistenza del modello `LegacyMigrationSync`**

```python
# in tests/backend/test_legacy_migration.py
def test_legacy_migration_sync_model_persistence(db_session):
    from models import LegacyMigrationSync
    record = LegacyMigrationSync(
        source_file="GestionaleReteBio2026.accdb",
        entity_type="partner",
        legacy_id="177",
        target_id=1,
        anno=2026
    )
    db_session.add(record)
    db_session.commit()
    assert record.id is not None
    assert record.entity_type == "partner"
```

- [ ] **Step 2: Eseguire il test per verificare il fallimento (RED)**

Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_legacy_migration.py -k test_legacy_migration_sync_model_persistence -v`
Expected: FAIL with `ImportError: cannot import name 'LegacyMigrationSync'`

- [ ] **Step 3: Implementare `LegacyMigrationSync` e registrarlo nei modelli**

Creare `backend/models/legacy_migration_sync.py` con `Base`, campi descritti nella spec e `UniqueConstraint('source_file', 'entity_type', 'legacy_id', name='uq_legacy_sync_source_entity_id')`. Importare ed esportare in `backend/models/__init__.py`. Generare la revisione Alembic con `alembic revision --autogenerate -m "add legacy migration sync model"` e applicare con `alembic upgrade head`.

- [ ] **Step 4: Eseguire il test per verificare il passaggio (GREEN)**

Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_legacy_migration.py -k test_legacy_migration_sync_model_persistence -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/models/legacy_migration_sync.py backend/models/__init__.py backend/migrations/versions/ tests/backend/test_legacy_migration.py
git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat(migration): modello LegacyMigrationSync e migrazione database"
```

---

### Task 2: Domain Service `LegacyMigrationService` (Estrazione, Normalizzazione e Idempotenza)

**Files:**
- Create: `backend/services/legacy_migration_service.py`
- Modify: `tests/backend/test_legacy_migration.py`

**Interfaces:**
- Consumes: `LegacyMigrationSync`, `Partner`, `Product`, `PurchaseDeliveryNote`, `Invoice`, `InvoiceInstallment`
- Produces: `LegacyMigrationService` con metodi `inspect_database`, `dry_run`, `extract_and_migrate_partners`, `extract_and_migrate_products`, `extract_and_migrate_stock_lots`, `extract_and_migrate_invoices_and_installments`, `run_full_migration`.

- [ ] **Step 1: Scrivere i test per inspect, parsing ed estrazione idempotente**

```python
# in tests/backend/test_legacy_migration.py
def test_inspect_and_dry_run_access_file(db_session):
    from services.legacy_migration_service import LegacyMigrationService
    db_path = "/Users/novellig/docker_images/gestionale_retebio/GestionaleReteBio2026.accdb"
    info = LegacyMigrationService.inspect_database(db_path)
    assert info["is_valid"] is True
    assert "T_AllaDataFA" in info["tables"]

    dry = LegacyMigrationService.dry_run(db_path)
    assert dry["partners_count"] > 0
    assert dry["products_count"] > 0
```

- [ ] **Step 2: Eseguire i test per verificare il fallimento (RED)**

Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_legacy_migration.py -k test_inspect_and_dry_run_access_file -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.legacy_migration_service'`

- [ ] **Step 3: Implementare `LegacyMigrationService`**

Implementare in `backend/services/legacy_migration_service.py`:
- Invocazione sicura di `mdb-export` (o `/opt/homebrew/bin/mdb-export`);
- Normalizzazione e sanitizzazione stringhe, date Access (`MM/DD/YY` vs `DD/MM/YY`);
- Migrazione di `Partner` (da `T_AllaDataFA`, `FattureElMese`, `produttore`);
- Migrazione di `Product` (da `Tabella1CReg`, `T_AllaDataFA`);
- Carico iniziale inventario giacenze `T2` (`PurchaseDeliveryNote` e `PurchaseDeliveryNoteItem`);
- Migrazione `Invoice` e `InvoiceInstallment`;
- Registrazione e lookup su `LegacyMigrationSync` per garantire zero duplicati al ri-eseguire del comando.

- [ ] **Step 4: Eseguire i test per verificare il passaggio (GREEN)**

Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_legacy_migration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/legacy_migration_service.py tests/backend/test_legacy_migration.py
git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat(migration): domain service LegacyMigrationService con estrazione Access e UPSERT"
```

---

### Task 3: Motore di Reset di Sistema Atomico (`reset_database`)

**Files:**
- Modify: `backend/services/legacy_migration_service.py`
- Modify: `tests/backend/test_legacy_migration.py`

**Interfaces:**
- Produces: `LegacyMigrationService.reset_database(db: Session, confirm_wipe: str) -> dict`

- [ ] **Step 1: Scrivere test per il reset controllato e la protezione dell'account Admin**

```python
# in tests/backend/test_legacy_migration.py
def test_reset_database_safety_token_and_user_preservation(db_session):
    from services.legacy_migration_service import LegacyMigrationService
    from models import User, Partner
    
    # 1. Token errato rifiutato
    with pytest.raises(Exception):
        LegacyMigrationService.reset_database(db_session, confirm_wipe="WRONG")

    # 2. Reset valido
    db_session.add(Partner(ragione_sociale="Da Cancellare", tipo="cliente"))
    db_session.commit()
    res = LegacyMigrationService.reset_database(db_session, confirm_wipe="RESET_ERP9LLI")
    assert res["status"] == "success"
    assert db_session.query(Partner).count() == 0
    assert db_session.query(User).count() > 0
```

- [ ] **Step 2: Eseguire il test per verificare il fallimento (RED)**

Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_legacy_migration.py -k test_reset_database_safety_token_and_user_preservation -v`
Expected: FAIL with `AttributeError: type object 'LegacyMigrationService' has no attribute 'reset_database'`

- [ ] **Step 3: Implementare `reset_database` in `LegacyMigrationService`**

Implementare la cancellazione atomica in ordine referenziale di tutte le tabelle transazionali e di catalogo, preservando `User` e ri-eseguendo i seed delle causali contabili base.

- [ ] **Step 4: Eseguire il test per verificare il passaggio (GREEN)**

Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_legacy_migration.py -k test_reset_database_safety_token_and_user_preservation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/legacy_migration_service.py tests/backend/test_legacy_migration.py
git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat(migration): procedura atomica di reset database con token di sicurezza"
```

---

### Task 4: Schemi Pydantic, Router FastAPI `/api/migration` e Notifiche Live

**Files:**
- Create: `backend/schemas/migration.py`
- Create: `backend/api/routers/migration.py`
- Modify: `backend/main.py`
- Modify: `tests/backend/test_legacy_migration.py`

**Interfaces:**
- Produces: Endpoints `POST /api/migration/inspect`, `POST /api/migration/dry-run`, `POST /api/migration/reset`, `POST /api/migration/execute`.

- [ ] **Step 1: Scrivere test di integrazione API per gli endpoint di migrazione**

```python
# in tests/backend/test_legacy_migration.py
def test_api_migration_endpoints(client, db_session, admin_headers):
    # inspect
    r = client.post("/api/migration/inspect", json={"source_file": "/Users/novellig/docker_images/gestionale_retebio/GestionaleReteBio2026.accdb"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["is_valid"] is True

    # dry-run
    r = client.post("/api/migration/dry-run", json={"source_file": "/Users/novellig/docker_images/gestionale_retebio/GestionaleReteBio2026.accdb"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["partners_count"] > 0
```

- [ ] **Step 2: Eseguire i test per verificare il fallimento (RED)**

Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_legacy_migration.py -k test_api_migration_endpoints -v`
Expected: FAIL with status 404 Not Found

- [ ] **Step 3: Implementare `schemas/migration.py`, `api/routers/migration.py` e collegare in `main.py`**

Creare gli schemi Pydantic v2, implementare il router con require_auth role Admin, emettere eventi via `event_dispatcher` con broadcast WebSocket per `execute`.

- [ ] **Step 4: Eseguire i test per verificare il passaggio (GREEN)**

Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/test_legacy_migration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/schemas/migration.py backend/api/routers/migration.py backend/main.py tests/backend/test_legacy_migration.py
git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat(migration): router FastAPI /api/migration con schemi Pydantic v2 e WebSocket"
```

---

### Task 5: Componente Frontend `LegacyMigration.vue`, Routing e Test Vitest

**Files:**
- Create: `frontend/src/components/LegacyMigration.vue`
- Modify: `frontend/src/router.js`
- Modify: `frontend/src/App.vue`
- Create: `tests/frontend/LegacyMigration.spec.js`

**Interfaces:**
- Produces: Interfaccia utente interattiva su `/legacy-migration` con supporto Dry-run, Reset con modal di conferma e barra di avanzamento real-time.

- [ ] **Step 1: Scrivere test frontend Vitest per `LegacyMigration.vue`**

```javascript
// in tests/frontend/LegacyMigration.spec.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import LegacyMigration from '../../frontend/src/components/LegacyMigration.vue'

describe('LegacyMigration.vue', () => {
  it('renders migration dashboard and controls correctly', async () => {
    const wrapper = mount(LegacyMigration, {
      global: {
        stubs: {
          'q-btn': true,
          'q-input': true,
          'q-card': true,
          'q-card-section': true,
          'q-card-actions': true,
          'q-dialog': true,
          'q-linear-progress': true,
          'q-badge': true,
          'q-banner': true,
          'q-toggle': true,
          'q-icon': true,
          'q-separator': true
        }
      }
    })
    expect(wrapper.text()).toContain('Inizializzazione & Migrazione Dati Legacy')
  })
})
```

- [ ] **Step 2: Eseguire il test Vitest per verificare il fallimento (RED)**

Run: `npm test --prefix frontend -- tests/frontend/LegacyMigration.spec.js`
Expected: FAIL with `Cannot find module ... LegacyMigration.vue`

- [ ] **Step 3: Implementare `LegacyMigration.vue`, registrare rotta in `router.js` e voce in `App.vue`**

Creare `frontend/src/components/LegacyMigration.vue` con Quasar:
- Card Parametri & Selezione Modalità (Incrementale vs Wipe);
- Card Anteprima / Dry Run con tabella statistiche;
- Card Esecuzione con `q-linear-progress` e console log live;
- Dialog modale di sicurezza per il Reset;
- Aggiornare `router.js` e aggiungere link nel drawer di navigazione in `App.vue`.

- [ ] **Step 4: Eseguire i test Vitest per verificare il passaggio (GREEN)**

Run: `npm test --prefix frontend -- tests/frontend/LegacyMigration.spec.js`
Expected: PASS

- [ ] **Step 5: Verificare intera test suite frontend e backend**

Run: `uv run --with-requirements backend/requirements.txt pytest tests/backend/ -q && npm test --prefix frontend`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/LegacyMigration.vue frontend/src/router.js frontend/src/App.vue tests/frontend/LegacyMigration.spec.js
git -c user.signingkey=8B91C26B23264F4407CD41343FD13DC88C48D7E0 commit -S -m "feat(ui): interfaccia grafica LegacyMigration.vue, routing e test vitest"
```
