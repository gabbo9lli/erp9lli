from datetime import datetime
from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class SystemEvent(Base):
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey('event_channel.id'), nullable=False)
    category_id = Column(Integer, ForeignKey('event_category.id'), nullable=True)
    event_type_id = Column(Integer, ForeignKey('event_type.id'), nullable=True)
    coda_nome = Column(String(30), nullable=True)
    rq_job_id = Column(String(50), nullable=True)
    livello = Column(String(20), nullable=False, default='info') # info, success, warning, error
    azione = Column(String(50), nullable=False) # emissione_ddt, sollecito_pallet, etc.
    titolo = Column(String(200), nullable=False)
    descrizione = Column(Text, nullable=True)
    payload_dati = Column(JSON, nullable=True)
    risultato_dati = Column(JSON, nullable=True)
    utente_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    utente_email = Column(String(120), nullable=True)
    partner_id = Column(Integer, ForeignKey('partner.id'), nullable=True)
    destinatario_recapito = Column(String(200), nullable=True)
    entita_tipo = Column(String(30), nullable=True)
    entita_id = Column(Integer, nullable=True)
    is_async = Column(Boolean, nullable=False, default=False)
    progresso = Column(Integer, nullable=False, default=0)
    stato = Column(String(20), nullable=False, default='in_coda') # in_coda, in_corso, completato, test, errore
    tentativi = Column(Integer, nullable=False, default=0)
    max_tentativi = Column(Integer, nullable=False, default=3)
    data_creazione = Column(DateTime, nullable=False, default=datetime.utcnow)
    data_inizio_esecuzione = Column(DateTime, nullable=True)
    data_completamento = Column(DateTime, nullable=True)
    note_esito = Column(Text, nullable=True)

    channel = relationship('EventChannel', backref='events', lazy='joined')
    category = relationship('EventCategory', backref='events', lazy='joined')
    event_type = relationship('EventType', backref='events', lazy='joined')
    user = relationship('User', backref='events')
    partner = relationship('Partner', backref='events')

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
            "event_type_id": self.event_type_id,
            "event_type_codice": self.event_type.codice if self.event_type else None,
            "coda_nome": self.coda_nome,
            "rq_job_id": self.rq_job_id,
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
