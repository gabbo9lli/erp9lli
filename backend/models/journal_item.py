from .base import db

class JournalItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entry.id', ondelete='CASCADE'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    partner_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=True)
    dare = db.Column(db.Float, nullable=False, default=0.0)
    avere = db.Column(db.Float, nullable=False, default=0.0)
    descrizione_riga = db.Column(db.String(200), nullable=True)

    account = db.relationship('Account')
    partner = db.relationship('Partner')

    def to_dict(self):
        return {
            "id": self.id,
            "journal_entry_id": self.journal_entry_id,
            "account_id": self.account_id,
            "account_codice": self.account.codice if self.account else None,
            "account_nome": self.account.nome if self.account else None,
            "partner_id": self.partner_id,
            "partner_nome": self.partner.ragione_sociale if self.partner else None,
            "dare": self.dare,
            "avere": self.avere,
            "descrizione_riga": self.descrizione_riga
        }
