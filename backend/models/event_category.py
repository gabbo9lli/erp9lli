from .base import db

class EventCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(30), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(100), nullable=False)
    colore_badge = db.Column(db.String(20), nullable=False, default='primary')
    icona = db.Column(db.String(30), nullable=False, default='info')
    attivo = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "codice": self.codice,
            "nome": self.nome,
            "colore_badge": self.colore_badge,
            "icona": self.icona,
            "attivo": self.attivo
        }
