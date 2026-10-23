from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey, Numeric
from sqlalchemy.orm import relationship, backref

class PosSaleItem(Base):
    id = Column(Integer, primary_key=True)
    pos_sale_id = Column(Integer, ForeignKey('pos_sale.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('product.id'), nullable=False)
    quantita = Column(Numeric(10, 3), nullable=False)
    prezzo_unitario = Column(Numeric(10, 2), nullable=False)
    aliquota_iva = Column(Numeric(5, 2), nullable=False, default=22.0)
    subtotale = Column(Numeric(10, 2), nullable=False)
    lotto = Column(String(50), nullable=True)
    data_scadenza = Column(Date, nullable=True)

    sale = relationship('PosSale', backref=backref('items', cascade='all, delete-orphan'))
    product = relationship('Product')

    def to_dict(self):
        return {
            "id": self.id,
            "pos_sale_id": self.pos_sale_id,
            "product_id": self.product_id,
            "product_codice": self.product.codice if self.product else None,
            "product_descrizione": self.product.descrizione if self.product else None,
            "quantita": float(self.quantita) if self.quantita is not None else 0.0,
            "prezzo_unitario": float(self.prezzo_unitario) if self.prezzo_unitario is not None else 0.0,
            "aliquota_iva": float(self.aliquota_iva) if self.aliquota_iva is not None else 22.0,
            "subtotale": float(self.subtotale) if self.subtotale is not None else 0.0,
            "lotto": self.lotto,
            "data_scadenza": self.data_scadenza.isoformat() if self.data_scadenza else None
        }
