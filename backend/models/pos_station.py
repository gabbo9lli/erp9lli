from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class PosStation(Base):
    id = Column(Integer, primary_key=True)
    codice = Column(String(30), unique=True, nullable=False, index=True)
    nome = Column(String(100), nullable=False)
    driver_tipo = Column(String(30), nullable=False, default='simulator') # simulator, epson_epos_http, custom_tcp, escpos_browser
    ip_address = Column(String(50), nullable=True)
    porta = Column(Integer, nullable=False, default=80)
    matricola_rt = Column(String(50), nullable=True)
    intestazione = Column(Text, nullable=True)
    pie_pagina = Column(Text, nullable=True)
    attivo = Column(Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "codice": self.codice,
            "nome": self.nome,
            "driver_tipo": self.driver_tipo,
            "ip_address": self.ip_address,
            "porta": self.porta,
            "matricola_rt": self.matricola_rt,
            "intestazione": self.intestazione,
            "pie_pagina": self.pie_pagina,
            "attivo": self.attivo
        }
