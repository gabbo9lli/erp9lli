from .base import db

class InvoiceInstallment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id', ondelete='CASCADE'), nullable=False)
    numero_rata = db.Column(db.Integer, nullable=False, default=1)
    totale_rate = db.Column(db.Integer, nullable=False, default=1)
    data_scadenza = db.Column(db.Date, nullable=False)
    importo = db.Column(db.Float, nullable=False)
    stato = db.Column(db.String(20), nullable=False, default='aperta') # aperta, incassata, scaduta
    data_incasso = db.Column(db.Date, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "numero_rata": self.numero_rata,
            "totale_rate": self.totale_rate,
            "data_scadenza": self.data_scadenza.isoformat() if self.data_scadenza else None,
            "importo": self.importo,
            "stato": self.stato,
            "data_incasso": self.data_incasso.isoformat() if self.data_incasso else None,
            "invoice_numero": self.invoice.numero_completo if self.invoice else None,
            "cliente_nome": self.invoice.cliente.ragione_sociale if self.invoice and self.invoice.cliente else None
        }
