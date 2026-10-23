from datetime import date
from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class JournalEntry(Base):
    id = Column(Integer, primary_key=True)
    numero = Column(Integer, nullable=False)
    anno = Column(Integer, nullable=False)
    numero_completo = Column(String(30), unique=True, nullable=False, index=True)
    data_registrazione = Column(Date, nullable=False, default=date.today)
    data_competenza = Column(Date, nullable=False, default=date.today)
    causale = Column(String(200), nullable=False)
    causale_id = Column(Integer, ForeignKey('accounting_causal.id'), nullable=True)
    totale_dare = Column(Float, nullable=False, default=0.0)
    totale_avere = Column(Float, nullable=False, default=0.0)
    stato = Column(String(20), nullable=False, default='confermata') # bozza, confermata
    note = Column(Text, nullable=True)

    causale_obj = relationship('AccountingCausal', backref='journal_entries')
    items = relationship('JournalItem', backref='entry', cascade='all, delete-orphan', passive_deletes=True)

    def to_dict(self):
        return {
            "id": self.id,
            "numero": self.numero,
            "anno": self.anno,
            "numero_completo": self.numero_completo,
            "data_registrazione": self.data_registrazione.isoformat() if self.data_registrazione else None,
            "data_competenza": self.data_competenza.isoformat() if self.data_competenza else None,
            "causale": self.causale,
            "causale_id": self.causale_id,
            "causale_codice": self.causale_obj.codice if self.causale_obj else None,
            "totale_dare": self.totale_dare,
            "totale_avere": self.totale_avere,
            "stato": self.stato,
            "note": self.note,
            "items": [item.to_dict() for item in self.items]
        }
