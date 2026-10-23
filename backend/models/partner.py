from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class Partner(Base):
    id = Column(Integer, primary_key=True)
    ragione_sociale = Column(String(150), nullable=False, index=True)
    tipo = Column(String(20), nullable=False, default='cliente') # cliente, fornitore, vettore, entrambi
    partita_iva = Column(String(20), nullable=True)
    codice_fiscale = Column(String(20), nullable=True)
    indirizzo = Column(String(200), nullable=True)
    cap = Column(String(10), nullable=True)
    citta = Column(String(100), nullable=True)
    provincia = Column(String(10), nullable=True)
    nazione = Column(String(5), nullable=False, default='IT')
    codice_sdi = Column(String(7), nullable=False, default='0000000')
    pec = Column(String(120), nullable=True)
    istituto_certificatore = Column(String(100), nullable=True)
    iban = Column(String(35), nullable=True)
    condizioni_pagamento = Column(String(50), nullable=False, default='30gg fm')
    attivo = Column(Boolean, nullable=False, default=True)

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
