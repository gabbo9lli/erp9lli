from datetime import date
from .base import db

class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)
    anno = db.Column(db.Integer, nullable=False)
    numero_completo = db.Column(db.String(30), unique=True, nullable=False, index=True)
    data_registrazione = db.Column(db.Date, nullable=False, default=date.today)
    data_competenza = db.Column(db.Date, nullable=False, default=date.today)
    causale = db.Column(db.String(200), nullable=False)
    causale_id = db.Column(db.Integer, db.ForeignKey('accounting_causal.id'), nullable=True)
    totale_dare = db.Column(db.Float, nullable=False, default=0.0)
    totale_avere = db.Column(db.Float, nullable=False, default=0.0)
    stato = db.Column(db.String(20), nullable=False, default='confermata') # bozza, confermata
    note = db.Column(db.Text, nullable=True)

    causale_obj = db.relationship('AccountingCausal', backref='journal_entries')
    items = db.relationship('JournalItem', backref='entry', cascade='all, delete-orphan', passive_deletes=True)

    def to_dict(self):
        return {
            "id": self.id,
            "numero": self.numero,
            "anno": self.anno,
            "numero_completo": self.numero_completo,
            "data_registrazione": self.data_registrazione.isoformat() if self.data_registrazione else None,
            "data_competenza": self.data_competenza.isoformat() if self.data_competenza else None,
            "causale": self.causale,
            "causale_id": self.causale_id,
            "causale_codice": self.causale_obj.codice if self.causale_obj else None,
            "totale_dare": self.totale_dare,
            "totale_avere": self.totale_avere,
            "stato": self.stato,
            "note": self.note,
            "items": [item.to_dict() for item in self.items]
        }
