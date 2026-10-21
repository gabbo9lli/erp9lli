from datetime import date, timedelta
from .base import db

class PalletReceipt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)
    anno = db.Column(db.Integer, nullable=False)
    numero_completo = db.Column(db.String(30), unique=True, nullable=False, index=True)
    data_emissione = db.Column(db.Date, nullable=False, default=date.today)
    data_limite_restituzione = db.Column(db.Date, nullable=False)
    partner_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=False)
    delivery_note_id = db.Column(db.Integer, db.ForeignKey('delivery_note.id'), nullable=True)
    tipo = db.Column(db.String(20), nullable=False, default='uscita') # uscita, rientro
    totale_consegnati = db.Column(db.Integer, nullable=False, default=0)
    totale_restituiti = db.Column(db.Integer, nullable=False, default=0)
    saldo_netto = db.Column(db.Integer, nullable=False, default=0)
    stato = db.Column(db.String(20), nullable=False, default='aperto') # aperto, saldato, fatturato
    note = db.Column(db.Text, nullable=True)

    partner = db.relationship('Partner', backref='buoni_pallet')
    delivery_note = db.relationship('DeliveryNote', backref='buoni_pallet')
    items = db.relationship('PalletReceiptItem', backref='receipt', cascade='all, delete-orphan', passive_deletes=True)

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
