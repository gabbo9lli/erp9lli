from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class Account(Base):
    id = Column(Integer, primary_key=True)
    codice = Column(String(20), unique=True, nullable=False, index=True)
    nome = Column(String(100), nullable=False)
    tipo = Column(String(20), nullable=False) # attivo, passivo, costi, ricavi
    attivo = Column(Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "codice": self.codice,
            "nome": self.nome,
            "tipo": self.tipo,
            "attivo": self.attivo
        }
