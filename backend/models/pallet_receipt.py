from datetime import date, timedelta
from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class PalletReceipt(Base):
    id = Column(Integer, primary_key=True)
    numero = Column(Integer, nullable=False)
    anno = Column(Integer, nullable=False)
    numero_completo = Column(String(30), unique=True, nullable=False, index=True)
    data_emissione = Column(Date, nullable=False, default=date.today)
    data_limite_restituzione = Column(Date, nullable=False)
    partner_id = Column(Integer, ForeignKey('partner.id'), nullable=False)
    delivery_note_id = Column(Integer, ForeignKey('delivery_note.id'), nullable=True)
    tipo = Column(String(20), nullable=False, default='uscita') # uscita, rientro
    totale_consegnati = Column(Integer, nullable=False, default=0)
    totale_restituiti = Column(Integer, nullable=False, default=0)
    saldo_netto = Column(Integer, nullable=False, default=0)
    stato = Column(String(20), nullable=False, default='aperto') # aperto, saldato, fatturato
    note = Column(Text, nullable=True)

    partner = relationship('Partner', backref='buoni_pallet')
    delivery_note = relationship('DeliveryNote', backref='buoni_pallet')
    items = relationship('PalletReceiptItem', backref='receipt', cascade='all, delete-orphan', passive_deletes=True)

    def to_dict(self):
        today = date.today()
        giorni_rimanenti = (self.data_limite_restituzione - today).days if self.data_limite_restituzione else None
        return {
            "id": self.id,
            "numero": self.numero,
            "anno": self.anno,
            "numero_completo": self.numero_completo,
            "data_emissione": self.data_emissione.isoformat() if self.data_emissione else None,
            "data_limite_restituzione": self.data_limite_restituzione.isoformat() if self.data_limite_restituzione else None,
            "giorni_rimanenti": giorni_rimanenti,
            "scaduto": giorni_rimanenti is not None and giorni_rimanenti < 0,
            "partner_id": self.partner_id,
            "partner": self.partner.to_dict() if self.partner else None,
            "delivery_note_id": self.delivery_note_id,
            "delivery_note_numero": self.delivery_note.numero_completo if self.delivery_note else None,
            "tipo": self.tipo,
            "totale_consegnati": self.totale_consegnati,
            "totale_restituiti": self.totale_restituiti,
            "saldo_netto": self.saldo_netto,
            "stato": self.stato,
            "note": self.note,
            "items": [it.to_dict() for it in self.items]
        }
