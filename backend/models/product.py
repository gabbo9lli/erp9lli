from .base import db

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(50), unique=True, nullable=False, index=True)
    descrizione = db.Column(db.String(200), nullable=False)
    descrizione_en = db.Column(db.String(200), nullable=True)
    categoria = db.Column(db.String(50), nullable=False, default='fresco') # fresco, trasformato, imballo
    unita_misura = db.Column(db.String(10), nullable=False, default='KG')
    peso_netto = db.Column(db.Float, nullable=False, default=0.0)
    peso_lordo = db.Column(db.Float, nullable=False, default=0.0)
    tara = db.Column(db.Float, nullable=False, default=0.0)
    in_scadenza = db.Column(db.Boolean, nullable=False, default=False)
    scorta_minima = db.Column(db.Float, nullable=False, default=0.0)
    prezzo_vendita = db.Column(db.Float, nullable=False, default=0.0)
    prezzo_acquisto = db.Column(db.Float, nullable=False, default=0.0)
    aliquota_iva = db.Column(db.Integer, nullable=False, default=4)
    codice_nc = db.Column(db.String(20), nullable=True)
    attivo = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "codice": self.codice,
            "descrizione": self.descrizione,
            "descrizione_en": self.descrizione_en,
            "categoria": self.categoria,
            "unita_misura": self.unita_misura,
            "peso_netto": self.peso_netto,
            "peso_lordo": self.peso_lordo,
            "tara": self.tara,
            "in_scadenza": self.in_scadenza,
            "scorta_minima": self.scorta_minima,
            "prezzo_vendita": self.prezzo_vendita,
            "prezzo_acquisto": self.prezzo_acquisto,
            "aliquota_iva": self.aliquota_iva,
            "codice_nc": self.codice_nc,
            "attivo": self.attivo
        }
