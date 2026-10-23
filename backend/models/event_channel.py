from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class EventChannel(Base):
    id = Column(Integer, primary_key=True)
    codice = Column(String(30), unique=True, nullable=False, index=True)
    nome = Column(String(100), nullable=False)
    descrizione = Column(Text, nullable=True)
    tipo_dispatcher = Column(String(30), nullable=False, default='internal') # internal, smtp, webhook
    configurazione = Column(JSON, nullable=True)
    richiede_destinatario = Column(Boolean, nullable=False, default=False)
    attivo = Column(Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "codice": self.codice,
            "nome": self.nome,
            "descrizione": self.descrizione,
            "tipo_dispatcher": self.tipo_dispatcher,
            "configurazione": self.configurazione,
            "richiede_destinatario": self.richiede_destinatario,
            "attivo": self.attivo
        }
