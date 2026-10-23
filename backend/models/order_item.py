from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class OrderItem(Base):
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('customer_order.id', ondelete='CASCADE'), nullable=False)
    product_id = Column(Integer, ForeignKey('product.id'), nullable=False)
    sequenza = Column(Integer, nullable=False, default=5)
    descrizione = Column(String(200), nullable=False)
    unita_misura = Column(String(10), nullable=False, default='KG')
    colli_ordinati = Column(Integer, nullable=False, default=1)
    quantita_ordinata = Column(Float, nullable=False)
    colli_consegnati = Column(Integer, nullable=False, default=0)
    quantita_consegnata = Column(Float, nullable=False, default=0.0)
    prezzo_unitario = Column(Float, nullable=False, default=0.0)
    aliquota_iva = Column(Integer, nullable=False, default=4)
    lotto = Column(String(50), nullable=True)
    stato = Column(String(20), nullable=False, default='aperto') # aperto, chiuso

    product = relationship('Product')

    @property
    def quantita_residua(self):
        return max(0.0, round(self.quantita_ordinata - self.quantita_consegnata, 2))

    @property
    def colli_residui(self):
        return max(0, self.colli_ordinati - self.colli_consegnati)

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "product_id": self.product_id,
            "product_codice": self.product.codice if self.product else None,
            "sequenza": self.sequenza,
            "descrizione": self.descrizione,
            "unita_misura": self.unita_misura,
            "colli_ordinati": self.colli_ordinati,
            "quantita_ordinata": self.quantita_ordinata,
            "colli_consegnati": self.colli_consegnati,
            "quantita_consegnata": self.quantita_consegnata,
            "colli_residui": self.colli_residui,
            "quantita_residua": self.quantita_residua,
            "prezzo_unitario": self.prezzo_unitario,
            "aliquota_iva": self.aliquota_iva,
            "lotto": self.lotto,
            "stato": self.stato
        }
