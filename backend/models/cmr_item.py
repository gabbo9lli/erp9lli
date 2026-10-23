from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class CmrItem(Base):
    id = Column(Integer, primary_key=True)
    cmr_document_id = Column(Integer, ForeignKey('cmr_document.id', ondelete='CASCADE'), nullable=False)
    riga_numero = Column(Integer, nullable=False, default=1)
    contrassegno_lotto = Column(String(50), nullable=True)
    numero_colli = Column(Integer, nullable=False, default=1)
    modo_imballaggio = Column(String(50), nullable=False, default='Casse su Pallet')
    natura_merce = Column(String(200), nullable=False)
    codice_nc = Column(String(20), nullable=True)
    peso_lordo_kg = Column(Float, nullable=False, default=0.0)
    peso_netto_kg = Column(Float, nullable=False, default=0.0)

    def to_dict(self):
        return {
            "id": self.id,
            "cmr_document_id": self.cmr_document_id,
            "riga_numero": self.riga_numero,
            "contrassegno_lotto": self.contrassegno_lotto,
            "numero_colli": self.numero_colli,
            "modo_imballaggio": self.modo_imballaggio,
            "natura_merce": self.natura_merce,
            "codice_nc": self.codice_nc,
            "peso_lordo_kg": self.peso_lordo_kg,
            "peso_netto_kg": self.peso_netto_kg
        }
