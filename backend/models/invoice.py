from datetime import date
from .base import db

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)
    anno = db.Column(db.Integer, nullable=False)
    numero_completo = db.Column(db.String(30), unique=True, nullable=False, index=True)
    tipo_documento = db.Column(db.String(10), nullable=False, default='TD24') # TD24 differita, TD01 immediata
    data_documento = db.Column(db.Date, nullable=False, default=date.today)
    cliente_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=False)
    condizioni_pagamento = db.Column(db.String(50), nullable=False, default='30gg fm')
    esigibilita_iva = db.Column(db.String(1), nullable=False, default='I') # I=immediata, D=differita, S=split payment
    totale_imponibile = db.Column(db.Float, nullable=False, default=0.0)
    totale_imposta = db.Column(db.Float, nullable=False, default=0.0)
    totale_fattura = db.Column(db.Float, nullable=False, default=0.0)
    castelletto_iva = db.Column(db.JSON, nullable=True)
    stato = db.Column(db.String(20), nullable=False, default='emessa') # bozza, emessa, inviata_sdi, saldata
    note = db.Column(db.Text, nullable=True)

    cliente = db.relationship('Partner', backref='fatture')
    items = db.relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan', passive_deletes=True)
    installments = db.relationship('InvoiceInstallment', backref='invoice', cascade='all, delete-orphan', passive_deletes=True, order_by='InvoiceInstallment.numero_rata')

    def to_dict(self):
        return {
            "id": self.id,
            "numero": self.numero,
            "anno": self.anno,
            "numero_completo": self.numero_completo,
            "tipo_documento": self.tipo_documento,
            "data_documento": self.data_documento.isoformat() if self.data_documento else None,
            "cliente_id": self.cliente_id,
            "cliente": self.cliente.to_dict() if self.cliente else None,
            "condizioni_pagamento": self.condizioni_pagamento,
            "esigibilita_iva": self.esigibilita_iva,
            "totale_imponibile": self.totale_imponibile,
            "totale_imposta": self.totale_imposta,
            "totale_fattura": self.totale_fattura,
            "castelletto_iva": self.castelletto_iva,
            "stato": self.stato,
            "note": self.note,
            "items": [item.to_dict() for item in self.items],
            "installments": [inst.to_dict() for inst in self.installments]
        }
