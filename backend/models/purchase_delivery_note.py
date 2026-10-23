from datetime import date
from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class PurchaseDeliveryNote(Base):
    id = Column(Integer, primary_key=True)
    numero_documento_fornitore = Column(String(50), nullable=False, index=True)
    data_documento = Column(Date, nullable=False)
    data_ricezione = Column(Date, nullable=False, default=date.today)
    fornitore_id = Column(Integer, ForeignKey('partner.id'), nullable=False)
    colli_totali = Column(Integer, nullable=False, default=0)
    peso_totale_netto = Column(Float, nullable=False, default=0.0)
    totale_imponibile = Column(Float, nullable=False, default=0.0)
    note = Column(Text, nullable=True)

    fornitore = relationship('Partner', backref='ddt_emessi_fornitore')
    items = relationship('PurchaseDeliveryNoteItem', backref='purchase_delivery_note', cascade='all, delete-orphan', passive_deletes=True)

    def to_dict(self):
        return {
            "id": self.id,
            "numero_documento_fornitore": self.numero_documento_fornitore,
            "data_documento": self.data_documento.isoformat() if self.data_documento else None,
            "data_ricezione": self.data_ricezione.isoformat() if self.data_ricezione else None,
            "fornitore_id": self.fornitore_id,
            "fornitore": self.fornitore.to_dict() if self.fornitore else None,
            "colli_totali": self.colli_totali,
            "peso_totale_netto": self.peso_totale_netto,
            "totale_imponibile": self.totale_imponibile,
            "note": self.note,
            "items": [it.to_dict() for it in self.items]
        }
