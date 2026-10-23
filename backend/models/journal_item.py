from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class JournalItem(Base):
    id = Column(Integer, primary_key=True)
    journal_entry_id = Column(Integer, ForeignKey('journal_entry.id', ondelete='CASCADE'), nullable=False)
    account_id = Column(Integer, ForeignKey('account.id'), nullable=False)
    partner_id = Column(Integer, ForeignKey('partner.id'), nullable=True)
    dare = Column(Float, nullable=False, default=0.0)
    avere = Column(Float, nullable=False, default=0.0)
    descrizione_riga = Column(String(200), nullable=True)

    account = relationship('Account')
    partner = relationship('Partner')

    def to_dict(self):
        return {
            "id": self.id,
            "journal_entry_id": self.journal_entry_id,
            "account_id": self.account_id,
            "account_codice": self.account.codice if self.account else None,
            "account_nome": self.account.nome if self.account else None,
            "partner_id": self.partner_id,
            "partner_nome": self.partner.ragione_sociale if self.partner else None,
            "dare": self.dare,
            "avere": self.avere,
            "descrizione_riga": self.descrizione_riga
        }
