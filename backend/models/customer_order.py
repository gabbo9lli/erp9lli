from datetime import date
from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class CustomerOrder(Base):
    id = Column(Integer, primary_key=True)
    numero = Column(Integer, nullable=False)
    anno = Column(Integer, nullable=False)
    numero_completo = Column(String(30), unique=True, nullable=False, index=True)
    data_ordine = Column(Date, nullable=False, default=date.today)
    data_richiesta = Column(Date, nullable=True)
    data_confermata = Column(Date, nullable=True)
    cliente_id = Column(Integer, ForeignKey('partner.id'), nullable=False)
    stato = Column(String(20), nullable=False, default='aperto') # aperto, in_lavorazione, chiuso
    totale_imponibile = Column(Float, nullable=False, default=0.0)
    note = Column(Text, nullable=True)
    external_reference = Column(String(100), nullable=True, index=True)
    canale_vendita = Column(String(30), nullable=False, server_default='diretto', default='diretto') # diretto, ecommerce, bancom

    cliente = relationship('Partner', backref='ordini_cliente')
    items = relationship('OrderItem', backref='order', cascade='all, delete-orphan', passive_deletes=True, order_by='OrderItem.sequenza')

    def to_dict(self):
        return {
            "id": self.id,
            "numero": self.numero,
            "anno": self.anno,
            "numero_completo": self.numero_completo,
            "data_ordine": self.data_ordine.isoformat() if self.data_ordine else None,
            "data_richiesta": self.data_richiesta.isoformat() if self.data_richiesta else None,
            "data_confermata": self.data_confermata.isoformat() if self.data_confermata else None,
            "cliente_id": self.cliente_id,
            "cliente": self.cliente.to_dict() if self.cliente else None,
            "stato": self.stato,
            "totale_imponibile": self.totale_imponibile,
            "note": self.note,
            "external_reference": self.external_reference,
            "canale_vendita": self.canale_vendita,
            "items": [it.to_dict() for it in self.items]
        }
