from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class PalletType(Base):
    id = Column(Integer, primary_key=True)
    codice = Column(String(20), unique=True, nullable=False, index=True)
    descrizione = Column(String(100), nullable=False)
    materiale = Column(String(20), nullable=False, default='legno') # legno, plastica
    valore_risarcimento = Column(Float, nullable=False, default=18.0)
    attivo = Column(Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "codice": self.codice,
            "descrizione": self.descrizione,
            "materiale": self.materiale,
            "valore_risarcimento": self.valore_risarcimento,
            "attivo": self.attivo
        }
