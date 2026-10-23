from datetime import date
from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship, backref

class Invoice(Base):
    id = Column(Integer, primary_key=True)
    numero = Column(Integer, nullable=False)
    anno = Column(Integer, nullable=False)
    numero_completo = Column(String(30), unique=True, nullable=False, index=True)
    tipo_documento = Column(String(10), nullable=False, default='TD24') # TD24 differita, TD01 immediata
    data_documento = Column(Date, nullable=False, default=date.today)
    cliente_id = Column(Integer, ForeignKey('partner.id'), nullable=False)
    condizioni_pagamento = Column(String(50), nullable=False, default='30gg fm')
    esigibilita_iva = Column(String(1), nullable=False, default='I') # I=immediata, D=differita, S=split payment
    totale_imponibile = Column(Float, nullable=False, default=0.0)
    totale_imposta = Column(Float, nullable=False, default=0.0)
    totale_fattura = Column(Float, nullable=False, default=0.0)
    castelletto_iva = Column(JSON, nullable=True)
    stato = Column(String(20), nullable=False, default='emessa') # bozza, emessa, inviata_sdi, saldata
    note = Column(Text, nullable=True)

    # Campi per Note di Credito (TD04) e Resi Merci
    invoice_origine_id = Column(Integer, ForeignKey('invoice.id'), nullable=True)
    invoice_origine_numero = Column(String(30), nullable=True)
    causale_storno = Column(Text, nullable=True)
    reintegro_magazzino = Column(Boolean, nullable=True, default=False)

    cliente = relationship('Partner', backref='fatture')
    invoice_origine = relationship('Invoice', remote_side=[id], backref=backref('note_credito', lazy='dynamic'))
    items = relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan', passive_deletes=True)
    installments = relationship('InvoiceInstallment', backref='invoice', cascade='all, delete-orphan', passive_deletes=True, order_by='InvoiceInstallment.numero_rata')

    def to_dict(self):
        return {
            "id": self.id,
            "numero": self.numero,
            "anno": self.anno,
            "numero_completo": self.numero_completo,
            "tipo_documento": self.tipo_documento,
            "data_documento": self.data_documento.isoformat() if self.data_documento else None,
            "cliente_id": self.cliente_id,
            "cliente": self.cliente.to_dict() if self.cliente else None,
            "condizioni_pagamento": self.condizioni_pagamento,
            "esigibilita_iva": self.esigibilita_iva,
            "totale_imponibile": self.totale_imponibile,
            "totale_imposta": self.totale_imposta,
            "totale_fattura": self.totale_fattura,
            "castelletto_iva": self.castelletto_iva,
            "stato": self.stato,
            "note": self.note,
            "invoice_origine_id": self.invoice_origine_id,
            "invoice_origine_numero": self.invoice_origine_numero,
            "causale_storno": self.causale_storno,
            "reintegro_magazzino": self.reintegro_magazzino,
            "items": [item.to_dict() for item in self.items],
            "installments": [inst.to_dict() for inst in self.installments]
        }
