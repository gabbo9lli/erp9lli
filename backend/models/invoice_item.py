from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class InvoiceItem(Base):
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey('invoice.id', ondelete='CASCADE'), nullable=False)
    delivery_note_id = Column(Integer, ForeignKey('delivery_note.id'), nullable=True)
    product_id = Column(Integer, ForeignKey('product.id'), nullable=False)
    descrizione = Column(String(200), nullable=False)
    unita_misura = Column(String(10), nullable=False, default='KG')
    colli = Column(Integer, nullable=False, default=1)
    quantita = Column(Float, nullable=False)
    prezzo_unitario = Column(Float, nullable=False, default=0.0)
    aliquota_iva = Column(Integer, nullable=False, default=4)
    imponibile_riga = Column(Float, nullable=False, default=0.0)
    lotto = Column(String(50), nullable=True)
    data_scadenza = Column(Date, nullable=True)

    product = relationship('Product')
    delivery_note = relationship('DeliveryNote')

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "delivery_note_id": self.delivery_note_id,
            "delivery_note_numero": self.delivery_note.numero_completo if self.delivery_note else None,
            "product_id": self.product_id,
            "product_codice": self.product.codice if self.product else None,
            "descrizione": self.descrizione,
            "unita_misura": self.unita_misura,
            "colli": self.colli,
            "quantita": self.quantita,
            "prezzo_unitario": self.prezzo_unitario,
            "aliquota_iva": self.aliquota_iva,
            "imponibile_riga": self.imponibile_riga,
            "lotto": self.lotto,
            "data_scadenza": self.data_scadenza.isoformat() if self.data_scadenza else None
        }
