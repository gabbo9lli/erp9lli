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


