from datetime import date
from .base import db

class DeliveryNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)
    anno = db.Column(db.Integer, nullable=False)
    numero_completo = db.Column(db.String(30), unique=True, nullable=False, index=True)
    data_documento = db.Column(db.Date, nullable=False, default=date.today)
    data_trasporto = db.Column(db.DateTime, nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=False)
    vettore_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=True)
    causale_trasporto = db.Column(db.String(50), nullable=False, default='Vendita')
    porto = db.Column(db.String(20), nullable=False, default='Franco')
    aspetto_beni = db.Column(db.String(50), nullable=False, default='Colli')
    colli_totali = db.Column(db.Integer, nullable=False, default=0)
    peso_totale_netto = db.Column(db.Float, nullable=False, default=0.0)
    peso_totale_lordo = db.Column(db.Float, nullable=False, default=0.0)
    totale_imponibile = db.Column(db.Float, nullable=False, default=0.0)
    stato = db.Column(db.String(20), nullable=False, default='bozza') # bozza, confermato, fatturato
    note = db.Column(db.Text, nullable=True)

    cliente = db.relationship('Partner', foreign_keys=[cliente_id], backref='ddt_ricevuti')
    vettore = db.relationship('Partner', foreign_keys=[vettore_id], backref='ddt_trasportati')
    items = db.relationship('DeliveryNoteItem', backref='delivery_note', cascade='all, delete-orphan', passive_deletes=True)

    def to_dict(self):
        return {
            "id": self.id,
            "numero": self.numero,
            "anno": self.anno,
            "numero_completo": self.numero_completo,
            "data_documento": self.data_documento.isoformat() if self.data_documento else None,
            "data_trasporto": self.data_trasporto.isoformat() if self.data_trasporto else None,
            "cliente_id": self.cliente_id,
            "cliente": self.cliente.to_dict() if self.cliente else None,
            "vettore_id": self.vettore_id,
            "vettore": self.vettore.to_dict() if self.vettore else None,
            "causale_trasporto": self.causale_trasporto,
            "porto": self.porto,
            "aspetto_beni": self.aspetto_beni,
            "colli_totali": self.colli_totali,
            "peso_totale_netto": self.peso_totale_netto,
            "peso_totale_lordo": self.peso_totale_lordo,
            "totale_imponibile": self.totale_imponibile,
            "stato": self.stato,
            "note": self.note,
            "items": [item.to_dict() for item in self.items]
        }
