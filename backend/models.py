from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from datetime import datetime, timedelta, date

# Define the naming convention
convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# Initialize SQLAlchemy with the convention
metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(metadata=metadata)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=True)
    # Add the new role column
    role = db.Column(db.String(20), default='User') 
    oauth_provider = db.Column(db.String(50), default='oidc', nullable=True)
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def get_reset_token(self):
        token = secrets.token_urlsafe(32)
        self.reset_token = token
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
        return token

class Partner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ragione_sociale = db.Column(db.String(150), nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False, default='cliente') # cliente, fornitore, vettore, entrambi
    partita_iva = db.Column(db.String(20), nullable=True)
    codice_fiscale = db.Column(db.String(20), nullable=True)
    indirizzo = db.Column(db.String(200), nullable=True)
    cap = db.Column(db.String(10), nullable=True)
    citta = db.Column(db.String(100), nullable=True)
    provincia = db.Column(db.String(10), nullable=True)
    nazione = db.Column(db.String(5), nullable=False, default='IT')
    codice_sdi = db.Column(db.String(7), nullable=False, default='0000000')
    pec = db.Column(db.String(120), nullable=True)
    istituto_certificatore = db.Column(db.String(100), nullable=True)
    iban = db.Column(db.String(35), nullable=True)
    condizioni_pagamento = db.Column(db.String(50), nullable=False, default='30gg fm')
    attivo = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "ragione_sociale": self.ragione_sociale,
            "tipo": self.tipo,
            "partita_iva": self.partita_iva,
            "codice_fiscale": self.codice_fiscale,
            "indirizzo": self.indirizzo,
            "cap": self.cap,
            "citta": self.citta,
            "provincia": self.provincia,
            "nazione": self.nazione,
            "codice_sdi": self.codice_sdi,
            "pec": self.pec,
            "istituto_certificatore": self.istituto_certificatore,
            "iban": self.iban,
            "condizioni_pagamento": self.condizioni_pagamento,
            "attivo": self.attivo
        }

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(50), unique=True, nullable=False, index=True)
    descrizione = db.Column(db.String(200), nullable=False)
    descrizione_en = db.Column(db.String(200), nullable=True)
    categoria = db.Column(db.String(50), nullable=False, default='fresco') # fresco, trasformato, imballo
    unita_misura = db.Column(db.String(10), nullable=False, default='KG')
    peso_netto = db.Column(db.Float, nullable=False, default=0.0)
    peso_lordo = db.Column(db.Float, nullable=False, default=0.0)
    tara = db.Column(db.Float, nullable=False, default=0.0)
    in_scadenza = db.Column(db.Boolean, nullable=False, default=False)
    scorta_minima = db.Column(db.Float, nullable=False, default=0.0)
    prezzo_vendita = db.Column(db.Float, nullable=False, default=0.0)
    prezzo_acquisto = db.Column(db.Float, nullable=False, default=0.0)
    aliquota_iva = db.Column(db.Integer, nullable=False, default=4)
    codice_nc = db.Column(db.String(20), nullable=True)
    attivo = db.Column(db.Boolean, nullable=False, default=True)

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

class DeliveryNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)
    anno = db.Column(db.Integer, nullable=False)
    numero_completo = db.Column(db.String(30), unique=True, nullable=False, index=True)
    data_documento = db.Column(db.Date, nullable=False, default=date.today)
    data_trasporto = db.Column(db.DateTime, nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=False)
    vettore_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=True)
    causale_trasporto = db.Column(db.String(50), nullable=False, default='Vendita')
    porto = db.Column(db.String(20), nullable=False, default='Franco')
    aspetto_beni = db.Column(db.String(50), nullable=False, default='Colli')
    colli_totali = db.Column(db.Integer, nullable=False, default=0)
    peso_totale_netto = db.Column(db.Float, nullable=False, default=0.0)
    peso_totale_lordo = db.Column(db.Float, nullable=False, default=0.0)
    totale_imponibile = db.Column(db.Float, nullable=False, default=0.0)
    stato = db.Column(db.String(20), nullable=False, default='bozza') # bozza, confermato, fatturato
    note = db.Column(db.Text, nullable=True)

    cliente = db.relationship('Partner', foreign_keys=[cliente_id], backref='ddt_ricevuti')
    vettore = db.relationship('Partner', foreign_keys=[vettore_id], backref='ddt_trasportati')
    items = db.relationship('DeliveryNoteItem', backref='delivery_note', cascade='all, delete-orphan', passive_deletes=True)

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

class DeliveryNoteItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    delivery_note_id = db.Column(db.Integer, db.ForeignKey('delivery_note.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    descrizione = db.Column(db.String(200), nullable=False)
    unita_misura = db.Column(db.String(10), nullable=False, default='KG')
    colli = db.Column(db.Integer, nullable=False, default=1)
    quantita = db.Column(db.Float, nullable=False)
    prezzo_unitario = db.Column(db.Float, nullable=False, default=0.0)
    aliquota_iva = db.Column(db.Integer, nullable=False, default=4)
    lotto = db.Column(db.String(50), nullable=True)
    data_scadenza = db.Column(db.Date, nullable=True)

    product = db.relationship('Product')

    def to_dict(self):
        return {
            "id": self.id,
            "delivery_note_id": self.delivery_note_id,
            "product_id": self.product_id,
            "product_codice": self.product.codice if self.product else None,
            "descrizione": self.descrizione,
            "unita_misura": self.unita_misura,
            "colli": self.colli,
            "quantita": self.quantita,
            "prezzo_unitario": self.prezzo_unitario,
            "aliquota_iva": self.aliquota_iva,
            "lotto": self.lotto,
            "data_scadenza": self.data_scadenza.isoformat() if self.data_scadenza else None,
            "in_scadenza": self.product.in_scadenza if self.product else False
        }