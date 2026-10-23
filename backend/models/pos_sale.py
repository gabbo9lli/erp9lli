from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime

class PosSale(Base):
    id = Column(Integer, primary_key=True)
    pos_station_id = Column(Integer, ForeignKey('pos_station.id'), nullable=False)
    numero_scontrino = Column(String(50), nullable=False, index=True)
    data_ora = Column(DateTime, nullable=False, default=datetime.utcnow)
    totale_lordo = Column(Numeric(12, 2), nullable=False)
    totale_imponibile = Column(Numeric(12, 2), nullable=False)
    totale_iva = Column(Numeric(12, 2), nullable=False)
    metodo_pagamento = Column(String(30), nullable=False) # contanti, pos_carta, misto
    importo_pagato = Column(Numeric(12, 2), nullable=False)
    importo_resto = Column(Numeric(12, 2), nullable=False, default=0.0)
    stato = Column(String(20), nullable=False, default='emesso') # emesso, annullato
    stato_fiscale_rt = Column(String(20), nullable=False, default='simulato') # simulato, stampato, errore
    dettaglio_rt_risposta = Column(Text, nullable=True)
    journal_entry_id = Column(Integer, ForeignKey('journal_entry.id'), nullable=True)
    utente_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    utente_email = Column(String(120), nullable=True)
    cliente_id = Column(Integer, ForeignKey('partner.id'), nullable=True)

    station = relationship('PosStation', backref='sales')
    journal_entry = relationship('JournalEntry', backref='pos_sales')
    cliente = relationship('Partner', backref='pos_sales')

    def to_dict(self):
        return {
            "id": self.id,
            "pos_station_id": self.pos_station_id,
            "pos_station_nome": self.station.nome if self.station else None,
            "pos_station_codice": self.station.codice if self.station else None,
            "numero_scontrino": self.numero_scontrino,
            "data_ora": self.data_ora.isoformat() if self.data_ora else None,
            "totale_lordo": float(self.totale_lordo) if self.totale_lordo is not None else 0.0,
            "totale_imponibile": float(self.totale_imponibile) if self.totale_imponibile is not None else 0.0,
            "totale_iva": float(self.totale_iva) if self.totale_iva is not None else 0.0,
            "metodo_pagamento": self.metodo_pagamento,
            "importo_pagato": float(self.importo_pagato) if self.importo_pagato is not None else 0.0,
            "importo_resto": float(self.importo_resto) if self.importo_resto is not None else 0.0,
            "stato": self.stato,
            "stato_fiscale_rt": self.stato_fiscale_rt,
            "dettaglio_rt_risposta": self.dettaglio_rt_risposta,
            "journal_entry_id": self.journal_entry_id,
            "utente_email": self.utente_email,
            "cliente_id": self.cliente_id,
            "cliente_ragione_sociale": self.cliente.ragione_sociale if self.cliente else "Cliente al Banco",
            "items": [item.to_dict() for item in self.items] if hasattr(self, 'items') and self.items else []
        }
