from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class PurchaseDeliveryNoteItem(Base):
    id = Column(Integer, primary_key=True)
    purchase_delivery_note_id = Column(Integer, ForeignKey('purchase_delivery_note.id', ondelete='CASCADE'), nullable=False)
    product_id = Column(Integer, ForeignKey('product.id'), nullable=False)
    descrizione = Column(String(200), nullable=False)
    unita_misura = Column(String(10), nullable=False, default='KG')
    colli = Column(Integer, nullable=False, default=1)
    quantita = Column(Float, nullable=False)
    prezzo_unitario = Column(Float, nullable=False, default=0.0)
    aliquota_iva = Column(Integer, nullable=False, default=4)
    lotto = Column(String(50), nullable=True)
    data_scadenza = Column(Date, nullable=True)

    product = relationship('Product')

    def to_dict(self):
        return {
            "id": self.id,
            "purchase_delivery_note_id": self.purchase_delivery_note_id,
            "product_id": self.product_id,
            "product_codice": self.product.codice if self.product else None,
            "descrizione": self.descrizione,
            "unita_misura": self.unita_misura,
            "colli": self.colli,
            "quantita": self.quantita,
            "prezzo_unitario": self.prezzo_unitario,
            "aliquota_iva": self.aliquota_iva,
            "lotto": self.lotto,
            "data_scadenza": self.data_scadenza.isoformat() if self.data_scadenza else None,
            "in_scadenza": self.product.in_scadenza if self.product else False
        }
