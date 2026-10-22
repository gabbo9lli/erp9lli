from .base import db

class EventType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(50), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(100), nullable=False)
    descrizione = db.Column(db.Text, nullable=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('event_channel.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('event_category.id'), nullable=True)
    accounting_causal_id = db.Column(db.Integer, db.ForeignKey('accounting_causal.id'), nullable=True)
    modalita_esecuzione = db.Column(db.String(20), nullable=False, default='sincrono') # sincrono, asincrono
    coda_nome = db.Column(db.String(30), nullable=False, default='default') # critical, emails, batch, default
    livello_default = db.Column(db.String(20), nullable=False, default='info')
    attivo = db.Column(db.Boolean, nullable=False, default=True)

    channel = db.relationship('EventChannel', backref='event_types')
    category = db.relationship('EventCategory', backref='event_types')
    accounting_causal = db.relationship('AccountingCausal', backref='event_types')

    def to_dict(self):
        return {
            "id": self.id,
            "codice": self.codice,
            "nome": self.nome,
            "descrizione": self.descrizione,
            "channel_id": self.channel_id,
            "channel_codice": self.channel.codice if self.channel else None,
            "category_id": self.category_id,
            "category_codice": self.category.codice if self.category else None,
            "category_nome": self.category.nome if self.category else None,
            "accounting_causal_id": self.accounting_causal_id,
            "accounting_causal_codice": self.accounting_causal.codice if self.accounting_causal else None,
            "modalita_esecuzione": self.modalita_esecuzione,
            "coda_nome": self.coda_nome,
            "livello_default": self.livello_default,
            "attivo": self.attivo
        }
