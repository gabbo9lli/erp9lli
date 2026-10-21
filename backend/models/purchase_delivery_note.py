from datetime import date
from .base import db

class PurchaseDeliveryNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_documento_fornitore = db.Column(db.String(50), nullable=False, index=True)
    data_documento = db.Column(db.Date, nullable=False)
    data_ricezione = db.Column(db.Date, nullable=False, default=date.today)
    fornitore_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=False)
    colli_totali = db.Column(db.Integer, nullable=False, default=0)
    peso_totale_netto = db.Column(db.Float, nullable=False, default=0.0)
    totale_imponibile = db.Column(db.Float, nullable=False, default=0.0)
    note = db.Column(db.Text, nullable=True)

    fornitore = db.relationship('Partner', backref='ddt_emessi_fornitore')
    items = db.relationship('PurchaseDeliveryNoteItem', backref='purchase_delivery_note', cascade='all, delete-orphan', passive_deletes=True)

    def to_dict(self):
        return {
            "id": self.id,
            "numero_documento_fornitore": self.numero_documento_fornitore,
            "data_documento": self.data_documento.isoformat() if self.data_documento else None,
            "data_ricezione": self.data_ricezione.isoformat() if self.data_ricezione else None,
            "fornitore_id": self.fornitore_id,
            "fornitore": self.fornitore.to_dict() if self.fornitore else None,
            "colli_totali": self.colli_totali,
            "peso_totale_netto": self.peso_totale_netto,
            "totale_imponibile": self.totale_imponibile,
            "note": self.note,
            "items": [it.to_dict() for it in self.items]
        }
