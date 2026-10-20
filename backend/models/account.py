from .base import db

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(20), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False) # attivo, passivo, costi, ricavi
    attivo = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "codice": self.codice,
            "nome": self.nome,
            "tipo": self.tipo,
            "attivo": self.attivo
        }
