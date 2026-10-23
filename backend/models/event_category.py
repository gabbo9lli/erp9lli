from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class EventCategory(Base):
    id = Column(Integer, primary_key=True)
    codice = Column(String(30), unique=True, nullable=False, index=True)
    nome = Column(String(100), nullable=False)
    colore_badge = Column(String(20), nullable=False, default='primary')
    icona = Column(String(30), nullable=False, default='info')
    attivo = Column(Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "codice": self.codice,
            "nome": self.nome,
            "colore_badge": self.colore_badge,
            "icona": self.icona,
            "attivo": self.attivo
        }
