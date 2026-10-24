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
