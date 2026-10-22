from datetime import datetime
from .base import db

class SystemEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('event_channel.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('event_category.id'), nullable=True)
    livello = db.Column(db.String(20), nullable=False, default='info') # info, success, warning, error
    azione = db.Column(db.String(50), nullable=False) # emissione_ddt, sollecito_pallet, etc.
    titolo = db.Column(db.String(200), nullable=False)
    descrizione = db.Column(db.Text, nullable=True)
    payload_dati = db.Column(db.JSON, nullable=True)
    risultato_dati = db.Column(db.JSON, nullable=True)
    utente_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    utente_email = db.Column(db.String(120), nullable=True)
    partner_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=True)
    destinatario_recapito = db.Column(db.String(200), nullable=True)
    entita_tipo = db.Column(db.String(30), nullable=True)
    entita_id = db.Column(db.Integer, nullable=True)
    is_async = db.Column(db.Boolean, nullable=False, default=False)
    progresso = db.Column(db.Integer, nullable=False, default=0)
    stato = db.Column(db.String(20), nullable=False, default='in_coda') # in_coda, in_corso, completato, test, errore
    tentativi = db.Column(db.Integer, nullable=False, default=0)
    max_tentativi = db.Column(db.Integer, nullable=False, default=3)
    data_creazione = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_inizio_esecuzione = db.Column(db.DateTime, nullable=True)
    data_completamento = db.Column(db.DateTime, nullable=True)
    note_esito = db.Column(db.Text, nullable=True)

    channel = db.relationship('EventChannel', backref='events')
    category = db.relationship('EventCategory', backref='events')
    user = db.relationship('User', backref='events')
    partner = db.relationship('Partner', backref='events')

    def to_dict(self):
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "channel_codice": self.channel.codice if self.channel else None,
            "channel_nome": self.channel.nome if self.channel else None,
            "category_id": self.category_id,
            "category_codice": self.category.codice if self.category else None,
            "category_nome": self.category.nome if self.category else None,
            "category_colore": self.category.colore_badge if self.category else 'primary',
            "category_icona": self.category.icona if self.category else 'info',
            "livello": self.livello,
            "azione": self.azione,
            "titolo": self.titolo,
            "descrizione": self.descrizione,
            "payload_dati": self.payload_dati,
            "risultato_dati": self.risultato_dati,
            "utente_id": self.utente_id,
            "utente_email": self.utente_email,
            "partner_id": self.partner_id,
            "partner_nome": self.partner.ragione_sociale if self.partner else None,
            "destinatario_recapito": self.destinatario_recapito,
            "entita_tipo": self.entita_tipo,
            "entita_id": self.entita_id,
            "is_async": self.is_async,
            "progresso": self.progresso,
            "stato": self.stato,
            "tentativi": self.tentativi,
            "data_creazione": self.data_creazione.isoformat() if self.data_creazione else None,
            "data_completamento": self.data_completamento.isoformat() if self.data_completamento else None,
            "note_esito": self.note_esito
        }
