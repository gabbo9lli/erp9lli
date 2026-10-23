from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class EcommerceSyncLog(Base):
    id = Column(Integer, primary_key=True)
    tipo_operazione = Column(String(30), nullable=False) # import_order, sync_stock, export_catalog
    external_order_id = Column(String(50), nullable=True, index=True)
    customer_order_id = Column(Integer, ForeignKey('customer_order.id'), nullable=True)
    stato = Column(String(20), nullable=False, default='success') # success, warning, error
    payload_ricevuto = Column(JSON, nullable=True)
    dettaglio_risposta = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    order = relationship('CustomerOrder', backref='ecommerce_sync_logs')

    def to_dict(self):
        return {
            "id": self.id,
            "tipo_operazione": self.tipo_operazione,
            "external_order_id": self.external_order_id,
            "customer_order_id": self.customer_order_id,
            "stato": self.stato,
            "payload_ricevuto": self.payload_ricevuto,
            "dettaglio_risposta": self.dettaglio_risposta,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
