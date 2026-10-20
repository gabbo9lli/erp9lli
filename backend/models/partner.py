from .base import db

class Partner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ragione_sociale = db.Column(db.String(150), nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False, default='cliente') # cliente, fornitore, vettore, entrambi
    partita_iva = db.Column(db.String(20), nullable=True)
    codice_fiscale = db.Column(db.String(20), nullable=True)
    indirizzo = db.Column(db.String(200), nullable=True)
    cap = db.Column(db.String(10), nullable=True)
    citta = db.Column(db.String(100), nullable=True)
    provincia = db.Column(db.String(10), nullable=True)
    nazione = db.Column(db.String(5), nullable=False, default='IT')
    codice_sdi = db.Column(db.String(7), nullable=False, default='0000000')
    pec = db.Column(db.String(120), nullable=True)
    istituto_certificatore = db.Column(db.String(100), nullable=True)
    iban = db.Column(db.String(35), nullable=True)
    condizioni_pagamento = db.Column(db.String(50), nullable=False, default='30gg fm')
    attivo = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "ragione_sociale": self.ragione_sociale,
            "tipo": self.tipo,
            "partita_iva": self.partita_iva,
            "codice_fiscale": self.codice_fiscale,
            "indirizzo": self.indirizzo,
            "cap": self.cap,
            "citta": self.citta,
            "provincia": self.provincia,
            "nazione": self.nazione,
            "codice_sdi": self.codice_sdi,
            "pec": self.pec,
            "istituto_certificatore": self.istituto_certificatore,
            "iban": self.iban,
            "condizioni_pagamento": self.condizioni_pagamento,
            "attivo": self.attivo
        }
