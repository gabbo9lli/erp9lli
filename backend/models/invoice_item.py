from .base import db

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id', ondelete='CASCADE'), nullable=False)
    delivery_note_id = db.Column(db.Integer, db.ForeignKey('delivery_note.id'), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    descrizione = db.Column(db.String(200), nullable=False)
    unita_misura = db.Column(db.String(10), nullable=False, default='KG')
    colli = db.Column(db.Integer, nullable=False, default=1)
    quantita = db.Column(db.Float, nullable=False)
    prezzo_unitario = db.Column(db.Float, nullable=False, default=0.0)
    aliquota_iva = db.Column(db.Integer, nullable=False, default=4)
    imponibile_riga = db.Column(db.Float, nullable=False, default=0.0)
    lotto = db.Column(db.String(50), nullable=True)
    data_scadenza = db.Column(db.Date, nullable=True)

    product = db.relationship('Product')
    delivery_note = db.relationship('DeliveryNote')

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
