from datetime import date
from .base import db

class CustomerOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)
    anno = db.Column(db.Integer, nullable=False)
    numero_completo = db.Column(db.String(30), unique=True, nullable=False, index=True)
    data_ordine = db.Column(db.Date, nullable=False, default=date.today)
    data_richiesta = db.Column(db.Date, nullable=True)
    data_confermata = db.Column(db.Date, nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=False)
    stato = db.Column(db.String(20), nullable=False, default='aperto') # aperto, in_lavorazione, chiuso
    totale_imponibile = db.Column(db.Float, nullable=False, default=0.0)
    note = db.Column(db.Text, nullable=True)

    cliente = db.relationship('Partner', backref='ordini_cliente')
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan', passive_deletes=True, order_by='OrderItem.sequenza')

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
            "items": [it.to_dict() for it in self.items]
        }
