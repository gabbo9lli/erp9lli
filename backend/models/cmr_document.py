from datetime import date
from .base import db

class CmrDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)
    anno = db.Column(db.Integer, nullable=False)
    numero_completo = db.Column(db.String(30), unique=True, nullable=False, index=True)
    data_documento = db.Column(db.Date, nullable=False, default=date.today)
    delivery_note_id = db.Column(db.Integer, db.ForeignKey('delivery_note.id'), nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=False)
    vettore_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=True)
    luogo_carico = db.Column(db.String(100), nullable=False, default='ALESSANDRIA (AL)')
    luogo_consegna = db.Column(db.String(200), nullable=False)
    targa_automezzo = db.Column(db.String(20), nullable=True)
    targa_rimorchio = db.Column(db.String(20), nullable=True)
    istruzioni_mittente = db.Column(db.Text, nullable=True)
    totale_colli = db.Column(db.Integer, nullable=False, default=0)
    peso_totale_netto = db.Column(db.Float, nullable=False, default=0.0)
    peso_totale_lordo = db.Column(db.Float, nullable=False, default=0.0)
    ha_allegato_righe = db.Column(db.Boolean, nullable=False, default=False)
    stato = db.Column(db.String(20), nullable=False, default='emesso') # bozza, emesso

    cliente = db.relationship('Partner', foreign_keys=[cliente_id], backref='cmr_ricevuti')
    vettore = db.relationship('Partner', foreign_keys=[vettore_id], backref='cmr_trasportati')
    delivery_note = db.relationship('DeliveryNote', backref='cmr_document')
    items = db.relationship('CmrItem', backref='document', cascade='all, delete-orphan', passive_deletes=True, order_by='CmrItem.riga_numero')

    def to_dict(self):
        return {
            "id": self.id,
            "numero": self.numero,
            "anno": self.anno,
            "numero_completo": self.numero_completo,
            "data_documento": self.data_documento.isoformat() if self.data_documento else None,
            "delivery_note_id": self.delivery_note_id,
            "delivery_note_numero": self.delivery_note.numero_completo if self.delivery_note else None,
            "cliente_id": self.cliente_id,
            "cliente": self.cliente.to_dict() if self.cliente else None,
            "vettore_id": self.vettore_id,
            "vettore": self.vettore.to_dict() if self.vettore else None,
            "luogo_carico": self.luogo_carico,
            "luogo_consegna": self.luogo_consegna,
            "targa_automezzo": self.targa_automezzo,
            "targa_rimorchio": self.targa_rimorchio,
            "istruzioni_mittente": self.istruzioni_mittente,
            "totale_colli": self.totale_colli,
            "peso_totale_netto": self.peso_totale_netto,
            "peso_totale_lordo": self.peso_totale_lordo,
            "ha_allegato_righe": self.ha_allegato_righe,
            "stato": self.stato,
            "items": [it.to_dict() for it in self.items]
        }
