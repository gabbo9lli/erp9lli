from .base import db

class AccountingCausal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(30), unique=True, nullable=False, index=True)
    descrizione = db.Column(db.String(150), nullable=False)
    tipo_registro = db.Column(db.String(30), nullable=False, default='generale') # vendite, acquisti, corrispettivi, generale
    conto_dare_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=True)
    conto_avere_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=True)
    conto_iva_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=True)
    template_descrizione = db.Column(db.String(200), nullable=True)
    attivo = db.Column(db.Boolean, nullable=False, default=True)

    conto_dare = db.relationship('Account', foreign_keys=[conto_dare_id])
    conto_avere = db.relationship('Account', foreign_keys=[conto_avere_id])
    conto_iva = db.relationship('Account', foreign_keys=[conto_iva_id])

    def to_dict(self):
        return {
            "id": self.id,
            "codice": self.codice,
            "descrizione": self.descrizione,
            "tipo_registro": self.tipo_registro,
            "conto_dare_id": self.conto_dare_id,
            "conto_dare_codice": self.conto_dare.codice if self.conto_dare else None,
            "conto_dare_nome": self.conto_dare.nome if self.conto_dare else None,
            "conto_avere_id": self.conto_avere_id,
            "conto_avere_codice": self.conto_avere.codice if self.conto_avere else None,
            "conto_avere_nome": self.conto_avere.nome if self.conto_avere else None,
            "conto_iva_id": self.conto_iva_id,
            "conto_iva_codice": self.conto_iva.codice if self.conto_iva else None,
            "conto_iva_nome": self.conto_iva.nome if self.conto_iva else None,
            "template_descrizione": self.template_descrizione,
            "attivo": self.attivo
        }
