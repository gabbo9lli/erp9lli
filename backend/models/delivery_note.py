from datetime import date
from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class DeliveryNote(Base):
    id = Column(Integer, primary_key=True)
    numero = Column(Integer, nullable=False)
    anno = Column(Integer, nullable=False)
    numero_completo = Column(String(30), unique=True, nullable=False, index=True)
    data_documento = Column(Date, nullable=False, default=date.today)
    data_trasporto = Column(DateTime, nullable=True)
    cliente_id = Column(Integer, ForeignKey('partner.id'), nullable=False)
    vettore_id = Column(Integer, ForeignKey('partner.id'), nullable=True)
    causale_trasporto = Column(String(50), nullable=False, default='Vendita')
    porto = Column(String(20), nullable=False, default='Franco')
    aspetto_beni = Column(String(50), nullable=False, default='Colli')
    colli_totali = Column(Integer, nullable=False, default=0)
    peso_totale_netto = Column(Float, nullable=False, default=0.0)
    peso_totale_lordo = Column(Float, nullable=False, default=0.0)
    totale_imponibile = Column(Float, nullable=False, default=0.0)
    stato = Column(String(20), nullable=False, default='bozza') # bozza, confermato, fatturato
    note = Column(Text, nullable=True)

    cliente = relationship('Partner', foreign_keys=[cliente_id], backref='ddt_ricevuti')
    vettore = relationship('Partner', foreign_keys=[vettore_id], backref='ddt_trasportati')
    items = relationship('DeliveryNoteItem', backref='delivery_note', cascade='all, delete-orphan', passive_deletes=True)

    def to_dict(self):
        return {
            "id": self.id,
            "numero": self.numero,
            "anno": self.anno,
            "numero_completo": self.numero_completo,
            "data_documento": self.data_documento.isoformat() if self.data_documento else None,
            "data_trasporto": self.data_trasporto.isoformat() if self.data_trasporto else None,
            "cliente_id": self.cliente_id,
            "cliente": self.cliente.to_dict() if self.cliente else None,
            "vettore_id": self.vettore_id,
            "vettore": self.vettore.to_dict() if self.vettore else None,
            "causale_trasporto": self.causale_trasporto,
            "porto": self.porto,
            "aspetto_beni": self.aspetto_beni,
            "colli_totali": self.colli_totali,
            "peso_totale_netto": self.peso_totale_netto,
            "peso_totale_lordo": self.peso_totale_lordo,
            "totale_imponibile": self.totale_imponibile,
            "stato": self.stato,
            "note": self.note,
            "items": [item.to_dict() for item in self.items]
        }
