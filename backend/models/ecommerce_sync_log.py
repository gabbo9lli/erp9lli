from .base import db
from datetime import datetime

class EcommerceSyncLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo_operazione = db.Column(db.String(30), nullable=False) # import_order, sync_stock, export_catalog
    external_order_id = db.Column(db.String(50), nullable=True, index=True)
    customer_order_id = db.Column(db.Integer, db.ForeignKey('customer_order.id'), nullable=True)
    stato = db.Column(db.String(20), nullable=False, default='success') # success, warning, error
    payload_ricevuto = db.Column(db.JSON, nullable=True)
    dettaglio_risposta = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    order = db.relationship('CustomerOrder', backref='ecommerce_sync_logs')

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
