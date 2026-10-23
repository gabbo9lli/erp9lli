from datetime import date
from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class CmrDocument(Base):
    id = Column(Integer, primary_key=True)
    numero = Column(Integer, nullable=False)
    anno = Column(Integer, nullable=False)
    numero_completo = Column(String(30), unique=True, nullable=False, index=True)
    data_documento = Column(Date, nullable=False, default=date.today)
    delivery_note_id = Column(Integer, ForeignKey('delivery_note.id'), nullable=True)
    cliente_id = Column(Integer, ForeignKey('partner.id'), nullable=False)
    vettore_id = Column(Integer, ForeignKey('partner.id'), nullable=True)
    luogo_carico = Column(String(100), nullable=False, default='ALESSANDRIA (AL)')
    luogo_consegna = Column(String(200), nullable=False)
    targa_automezzo = Column(String(20), nullable=True)
    targa_rimorchio = Column(String(20), nullable=True)
    istruzioni_mittente = Column(Text, nullable=True)
    totale_colli = Column(Integer, nullable=False, default=0)
    peso_totale_netto = Column(Float, nullable=False, default=0.0)
    peso_totale_lordo = Column(Float, nullable=False, default=0.0)
    ha_allegato_righe = Column(Boolean, nullable=False, default=False)
    stato = Column(String(20), nullable=False, default='emesso') # bozza, emesso

    cliente = relationship('Partner', foreign_keys=[cliente_id], backref='cmr_ricevuti')
    vettore = relationship('Partner', foreign_keys=[vettore_id], backref='cmr_trasportati')
    delivery_note = relationship('DeliveryNote', backref='cmr_document')
    items = relationship('CmrItem', backref='document', cascade='all, delete-orphan', passive_deletes=True, order_by='CmrItem.riga_numero')

    def to_dict(self):
        return {
            "id": self.id,
            "numero": self.numero,
            "anno": self.anno,
            "numero_completo": self.numero_completo,
            "data_documento": self.data_documento.isoformat() if self.data_documento else None,
            "delivery_note_id": self.delivery_note_id,
            "delivery_note_numero": self.delivery_note.numero_completo if self.delivery_note else None,
            "cliente_id": self.cliente_id,
            "cliente": self.cliente.to_dict() if self.cliente else None,
            "vettore_id": self.vettore_id,
            "vettore": self.vettore.to_dict() if self.vettore else None,
            "luogo_carico": self.luogo_carico,
            "luogo_consegna": self.luogo_consegna,
            "targa_automezzo": self.targa_automezzo,
            "targa_rimorchio": self.targa_rimorchio,
            "istruzioni_mittente": self.istruzioni_mittente,
            "totale_colli": self.totale_colli,
            "peso_totale_netto": self.peso_totale_netto,
            "peso_totale_lordo": self.peso_totale_lordo,
            "ha_allegato_righe": self.ha_allegato_righe,
            "stato": self.stato,
            "items": [it.to_dict() for it in self.items]
        }
