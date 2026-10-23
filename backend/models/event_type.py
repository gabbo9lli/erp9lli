from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class EventType(Base):
    id = Column(Integer, primary_key=True)
    codice = Column(String(50), unique=True, nullable=False, index=True)
    nome = Column(String(100), nullable=False)
    descrizione = Column(Text, nullable=True)
    channel_id = Column(Integer, ForeignKey('event_channel.id'), nullable=False)
    category_id = Column(Integer, ForeignKey('event_category.id'), nullable=True)
    accounting_causal_id = Column(Integer, ForeignKey('accounting_causal.id'), nullable=True)
    modalita_esecuzione = Column(String(20), nullable=False, default='sincrono') # sincrono, asincrono
    coda_nome = Column(String(30), nullable=False, default='default') # critical, emails, batch, default
    livello_default = Column(String(20), nullable=False, default='info')
    attivo = Column(Boolean, nullable=False, default=True)

    channel = relationship('EventChannel', backref='event_types')
    category = relationship('EventCategory', backref='event_types')
    accounting_causal = relationship('AccountingCausal', backref='event_types')

    def to_dict(self):
        return {
            "id": self.id,
            "codice": self.codice,
            "nome": self.nome,
            "descrizione": self.descrizione,
            "channel_id": self.channel_id,
            "channel_codice": self.channel.codice if self.channel else None,
            "category_id": self.category_id,
            "category_codice": self.category.codice if self.category else None,
            "category_nome": self.category.nome if self.category else None,
            "accounting_causal_id": self.accounting_causal_id,
            "accounting_causal_codice": self.accounting_causal.codice if self.accounting_causal else None,
            "modalita_esecuzione": self.modalita_esecuzione,
            "coda_nome": self.coda_nome,
            "livello_default": self.livello_default,
            "attivo": self.attivo
        }
