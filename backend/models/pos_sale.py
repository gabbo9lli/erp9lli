from .base import db
from datetime import datetime

class PosSale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pos_station_id = db.Column(db.Integer, db.ForeignKey('pos_station.id'), nullable=False)
    numero_scontrino = db.Column(db.String(50), nullable=False, index=True)
    data_ora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    totale_lordo = db.Column(db.Numeric(12, 2), nullable=False)
    totale_imponibile = db.Column(db.Numeric(12, 2), nullable=False)
    totale_iva = db.Column(db.Numeric(12, 2), nullable=False)
    metodo_pagamento = db.Column(db.String(30), nullable=False) # contanti, pos_carta, misto
    importo_pagato = db.Column(db.Numeric(12, 2), nullable=False)
    importo_resto = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    stato = db.Column(db.String(20), nullable=False, default='emesso') # emesso, annullato
    stato_fiscale_rt = db.Column(db.String(20), nullable=False, default='simulato') # simulato, stampato, errore
    dettaglio_rt_risposta = db.Column(db.Text, nullable=True)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entry.id'), nullable=True)
    utente_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    utente_email = db.Column(db.String(120), nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=True)

    station = db.relationship('PosStation', backref='sales')
    journal_entry = db.relationship('JournalEntry', backref='pos_sales')
    cliente = db.relationship('Partner', backref='pos_sales')

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
