from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class Product(Base):
    id = Column(Integer, primary_key=True)
    codice = Column(String(50), unique=True, nullable=False, index=True)
    descrizione = Column(String(200), nullable=False)
    descrizione_en = Column(String(200), nullable=True)
    categoria = Column(String(50), nullable=False, default='fresco') # fresco, trasformato, imballo
    unita_misura = Column(String(10), nullable=False, default='KG')
    peso_netto = Column(Float, nullable=False, default=0.0)
    peso_lordo = Column(Float, nullable=False, default=0.0)
    tara = Column(Float, nullable=False, default=0.0)
    in_scadenza = Column(Boolean, nullable=False, default=False)
    scorta_minima = Column(Float, nullable=False, default=0.0)
    prezzo_vendita = Column(Float, nullable=False, default=0.0)
    prezzo_acquisto = Column(Float, nullable=False, default=0.0)
    aliquota_iva = Column(Integer, nullable=False, default=4)
    codice_nc = Column(String(20), nullable=True)
    attivo = Column(Boolean, nullable=False, default=True)

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
