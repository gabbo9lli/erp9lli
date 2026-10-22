from .base import db

class PosStation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(30), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(100), nullable=False)
    driver_tipo = db.Column(db.String(30), nullable=False, default='simulator') # simulator, epson_epos_http, custom_tcp, escpos_browser
    ip_address = db.Column(db.String(50), nullable=True)
    porta = db.Column(db.Integer, nullable=False, default=80)
    matricola_rt = db.Column(db.String(50), nullable=True)
    intestazione = db.Column(db.Text, nullable=True)
    pie_pagina = db.Column(db.Text, nullable=True)
    attivo = db.Column(db.Boolean, nullable=False, default=True)

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
