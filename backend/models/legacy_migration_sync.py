from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from .base import Base

class LegacyMigrationSync(Base):
    __tablename__ = 'legacy_migration_sync'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_file = Column(String(255), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    legacy_id = Column(String(100), nullable=False, index=True)
    target_id = Column(Integer, nullable=False, index=True)
    anno = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('source_file', 'entity_type', 'legacy_id', name='uq_legacy_sync_source_entity_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'source_file': self.source_file,
            'entity_type': self.entity_type,
            'legacy_id': self.legacy_id,
            'target_id': self.target_id,
            'anno': self.anno,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
