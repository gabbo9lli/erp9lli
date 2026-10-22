from .base import db

class EventChannel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(30), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(100), nullable=False)
    descrizione = db.Column(db.Text, nullable=True)
    tipo_dispatcher = db.Column(db.String(30), nullable=False, default='internal') # internal, smtp, webhook
    configurazione = db.Column(db.JSON, nullable=True)
    richiede_destinatario = db.Column(db.Boolean, nullable=False, default=False)
    attivo = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "codice": self.codice,
            "nome": self.nome,
            "descrizione": self.descrizione,
            "tipo_dispatcher": self.tipo_dispatcher,
            "configurazione": self.configurazione,
            "richiede_destinatario": self.richiede_destinatario,
            "attivo": self.attivo
        }
