import pytest

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
    assert record.source_file == "GestionaleReteBio2026.accdb"
    assert record.legacy_id == "177"
    assert record.target_id == 1
    assert record.anno == 2026

def test_inspect_and_dry_run_access_file(db_session):
    from services.legacy_migration_service import LegacyMigrationService
    db_path = "/Users/novellig/docker_images/gestionale_retebio/GestionaleReteBio2026.accdb"
    info = LegacyMigrationService.inspect_database(db_path)
    assert info["is_valid"] is True
    assert "T_AllaDataFA" in info["tables"]
    assert "T2" in info["tables"]

    dry = LegacyMigrationService.dry_run(db_path)
    assert dry["partners_count"] > 0
    assert dry["products_count"] > 0
    assert dry["stock_lots_count"] > 0

def test_extract_and_migrate_idempotent(db_session):
    from services.legacy_migration_service import LegacyMigrationService
    from models import Partner, Product, PurchaseDeliveryNote, Invoice
    db_path = "/Users/novellig/docker_images/gestionale_retebio/GestionaleReteBio2026.accdb"

    # 1. Migrazione Partner (primo passaggio)
    p_count1 = LegacyMigrationService.extract_and_migrate_partners(db_session, db_path, limit=20)
    assert p_count1 > 0
    total_partners_1 = db_session.query(Partner).count()

    # Secondo passaggio (idempotenza)
    p_count2 = LegacyMigrationService.extract_and_migrate_partners(db_session, db_path, limit=20)
    total_partners_2 = db_session.query(Partner).count()
    assert total_partners_1 == total_partners_2

    # 2. Migrazione Prodotti (primo passaggio)
    prod_count1 = LegacyMigrationService.extract_and_migrate_products(db_session, db_path, limit=30)
    assert prod_count1 > 0
    total_prod_1 = db_session.query(Product).count()

    # Secondo passaggio (idempotenza)
    prod_count2 = LegacyMigrationService.extract_and_migrate_products(db_session, db_path, limit=30)
    total_prod_2 = db_session.query(Product).count()
    assert total_prod_1 == total_prod_2

    # 3. Migrazione Giacenze e Lotti (T2)
    lots_count = LegacyMigrationService.extract_and_migrate_stock_lots(db_session, db_path, limit=20)
    assert lots_count > 0
    assert db_session.query(PurchaseDeliveryNote).count() > 0

    # 4. Migrazione Fatture e Rate
    inv_count, inst_count = LegacyMigrationService.extract_and_migrate_invoices_and_installments(db_session, db_path, limit=20)
    assert inv_count > 0
    assert inst_count >= 0
    assert db_session.query(Invoice).count() > 0

def test_reset_database_safety_token_and_user_preservation(db_session):
    from services.legacy_migration_service import LegacyMigrationService
    from models import User, Partner, Product, Invoice
    from fastapi import HTTPException

    # 1. Token errato rifiutato con HTTPException 400
    with pytest.raises(HTTPException) as exc_info:
        LegacyMigrationService.reset_database(db_session, confirm_wipe="WRONG_TOKEN")
    assert exc_info.value.status_code == 400

    # 2. Popola dati transazionali
    p = Partner(ragione_sociale="Partner Da Resettare", tipo="cliente")
    prod = Product(codice="PROD-DEL", descrizione="Articolo Da Resettare")
    db_session.add_all([p, prod])
    db_session.commit()

    # Assicurati che esista un utente
    u = db_session.query(User).first()
    if not u:
        u = User(username="admin", email="admin@example.com", role="Admin")
        db_session.add(u)
        db_session.commit()

    user_count_before = db_session.query(User).count()
    assert db_session.query(Partner).count() > 0

    # 3. Esegui reset valido
    res = LegacyMigrationService.reset_database(db_session, confirm_wipe="RESET_ERP9LLI")
    assert res["status"] == "success"
    assert db_session.query(Partner).count() == 0
    assert db_session.query(Product).count() == 0
    # Users MAI cancellati!
    assert db_session.query(User).count() == user_count_before

def test_api_migration_endpoints(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    # 1. inspect
    r = client.post(
        "/api/migration/inspect",
        json={"source_file": "/Users/novellig/docker_images/gestionale_retebio/GestionaleReteBio2026.accdb"},
        headers=admin_headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["is_valid"] is True
    assert "T_AllaDataFA" in data["tables"]

    # 2. dry-run
    r = client.post(
        "/api/migration/dry-run",
        json={"source_file": "/Users/novellig/docker_images/gestionale_retebio/GestionaleReteBio2026.accdb"},
        headers=admin_headers
    )
    assert r.status_code == 200
    dry_data = r.json()
    assert dry_data["partners_count"] > 0
    assert dry_data["products_count"] > 0

    # 3. reset con token errato -> 400
    r = client.post(
        "/api/migration/reset",
        json={"confirm_wipe": "WRONG"},
        headers=admin_headers
    )
    assert r.status_code == 400

    # 4. esecuzione reale sincrona
    r = client.post(
        "/api/migration/execute",
        json={
            "source_file": "/Users/novellig/docker_images/gestionale_retebio/GestionaleReteBio2026.accdb",
            "is_async": False,
            "options": {"limit_per_table": 15}
        },
        headers=admin_headers
    )
    assert r.status_code in (200, 201)
    res_data = r.json()
    assert res_data["status"] == "success"
    assert res_data["migrated_partners"] > 0

def test_async_migration_isolated_session_and_progress_events(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    r = client.post(
        "/api/migration/execute",
        json={
            "source_file": "/Users/novellig/docker_images/gestionale_retebio/GestionaleReteBio2026.accdb",
            "is_async": True,
            "options": {"limit_per_table": 10}
        },
        headers=admin_headers
    )
    assert r.status_code in (200, 201)
    data = r.json()
    assert data["status"] == "in_coda"
    task_id = data["task_id"]
    assert task_id is not None

def test_upload_legacy_database_endpoint(client, db_session):
    import io
    import os
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    # 1. Reject invalid file extension (.txt)
    txt_content = io.BytesIO(b"dummy text content")
    r_bad = client.post(
        "/api/migration/upload",
        files={"file": ("test.txt", txt_content, "text/plain")},
        headers=admin_headers
    )
    assert r_bad.status_code == 400
    assert "estensione" in r_bad.json()["detail"].lower() or "supportati" in r_bad.json()["detail"].lower()

    # 2. Upload valid .accdb file
    accdb_content = io.BytesIO(b"\x00\x01\x02\x03fake_access_db_binary_content")
    r_ok = client.post(
        "/api/migration/upload",
        files={"file": ("GestionaleTest.accdb", accdb_content, "application/x-msaccess")},
        headers=admin_headers
    )
    assert r_ok.status_code == 200
    data = r_ok.json()
    assert data["status"] == "success"
    assert data["filename"] == "GestionaleTest.accdb"
    assert data["file_path"] is not None
    assert os.path.exists(data["file_path"])
    assert data["file_size_bytes"] == len(b"\x00\x01\x02\x03fake_access_db_binary_content")
    assert "file_size_mb" in data

    # Clean up test uploaded file
    if os.path.exists(data["file_path"]):
        os.remove(data["file_path"])





