from .base import db

class PalletReceiptItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pallet_receipt_id = db.Column(db.Integer, db.ForeignKey('pallet_receipt.id', ondelete='CASCADE'), nullable=False)
    pallet_type_id = db.Column(db.Integer, db.ForeignKey('pallet_type.id'), nullable=False)
    quantita_consegnata = db.Column(db.Integer, nullable=False, default=0)
    quantita_restituita = db.Column(db.Integer, nullable=False, default=0)
    saldo_riga = db.Column(db.Integer, nullable=False, default=0)

    pallet_type = db.relationship('PalletType')

    def to_dict(self):
        return {
            "id": self.id,
            "pallet_receipt_id": self.pallet_receipt_id,
            "pallet_type_id": self.pallet_type_id,
            "pallet_type_codice": self.pallet_type.codice if self.pallet_type else None,
            "pallet_type_descrizione": self.pallet_type.descrizione if self.pallet_type else None,
            "valore_risarcimento": self.pallet_type.valore_risarcimento if self.pallet_type else 0.0,
            "quantita_consegnata": self.quantita_consegnata,
            "quantita_restituita": self.quantita_restituita,
            "saldo_riga": self.saldo_riga
        }
