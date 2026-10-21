from .base import db

class PalletType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(20), unique=True, nullable=False, index=True)
    descrizione = db.Column(db.String(100), nullable=False)
    materiale = db.Column(db.String(20), nullable=False, default='legno') # legno, plastica
    valore_risarcimento = db.Column(db.Float, nullable=False, default=18.0)
    attivo = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "codice": self.codice,
            "descrizione": self.descrizione,
            "materiale": self.materiale,
            "valore_risarcimento": self.valore_risarcimento,
            "attivo": self.attivo
        }
