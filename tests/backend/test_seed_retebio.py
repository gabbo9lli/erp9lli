import pytest
from models import db, Partner, Product
import sys
import os

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from seed_retebio import seed_data

def test_seed_retebio_execution_and_idempotency(client):
    with client.application.app_context():
        # First execution: should populate partners and products
        added_partners, added_products = seed_data()
        assert added_partners > 5
        assert added_products > 5

        # Check partners diversity
        partners = Partner.query.all()
        tipi = {p.tipo for p in partners}
        assert 'cliente' in tipi
        assert 'fornitore' in tipi
        assert 'vettore' in tipi

        # Check SDI and tax data
        natura_si = Partner.query.filter(Partner.ragione_sociale.ilike('%NaturaSì%')).first()
        assert natura_si is not None
        assert natura_si.codice_sdi != "0000000"
        assert natura_si.partita_iva is not None

        # Check products diversity
        products = Product.query.all()
        categorie = {p.categoria for p in products}
        assert 'fresco' in categorie
        assert 'trasformato' in categorie
        assert 'imballo' in categorie

        # Check Bio expiration flag on fresh produce
        fresh = Product.query.filter_by(categoria='fresco').first()
        assert fresh is not None
        assert fresh.in_scadenza is True
        assert fresh.aliquota_iva == 4

        # Check pallet imballo
        pallet = Product.query.filter(Product.codice.ilike('%EPAL%')).first()
        assert pallet is not None
        assert pallet.categoria == 'imballo'

        # Second execution: should be idempotent and not insert duplicates
        added_p2, added_prod2 = seed_data()
        assert added_p2 == 0
        assert added_prod2 == 0
