import pytest
from models import Partner, Product

def test_partner_model_creation(client, db_session):
    p = Partner(
        ragione_sociale="Azienda Agricola Bio",
        tipo="fornitore",
        partita_iva="IT12345678901",
        citta="Reggio Emilia",
        provincia="RE"
    )
    db_session.add(p)
    db_session.commit()
    assert p.id is not None
    assert p.codice_sdi == "0000000"
    assert p.nazione == "IT"
    assert p.attivo is True

def test_product_model_creation(client, db_session):
    prod = Product(
        codice="BIO-MELA",
        descrizione="Mele Golden Bio",
        categoria="fresco",
        prezzo_vendita=2.50,
        prezzo_acquisto=1.20,
        aliquota_iva=4
    )
    db_session.add(prod)
    db_session.commit()
    assert prod.id is not None
    assert prod.in_scadenza is False
    assert prod.unita_misura == "KG"
    assert prod.attivo is True

def test_api_partners_crud(client, db_session):
    admin_headers = {
        'X-Forwarded-Email': 'admin@company.com',
        'X-Forwarded-Groups': 'admin'
    }
    client.get('/api/me', headers=admin_headers)

    # 1. Create Partner
    partner_data = {
        "ragione_sociale": "BioMarket Srl",
        "tipo": "cliente",
        "partita_iva": "IT98765432109",
        "codice_fiscale": "98765432109",
        "citta": "Bologna",
        "provincia": "BO",
        "codice_sdi": "M5UXCR1",
        "pec": "biomarket@pec.it"
    }
    create_res = client.post('/api/partners', json=partner_data, headers=admin_headers)
    assert create_res.status_code == 201
    created_id = create_res.json()['id']

    # 2. Get Partners with filter
    list_res = client.get('/api/partners?tipo=cliente', headers=admin_headers)
    assert list_res.status_code == 200
    partners = list_res.json()
    assert any(p['ragione_sociale'] == "BioMarket Srl" for p in partners)

    # 3. Update Partner
    update_res = client.put(f'/api/partners/{created_id}', json={"citta": "Modena", "provincia": "MO"}, headers=admin_headers)
    assert update_res.status_code == 200
    assert update_res.json()['citta'] == "Modena"

    # 4. Delete / Deactivate Partner
    del_res = client.delete(f'/api/partners/{created_id}', headers=admin_headers)
    assert del_res.status_code == 200

def test_api_products_crud(client, db_session):
    admin_headers = {
        'X-Forwarded-Email': 'admin@company.com',
        'X-Forwarded-Groups': 'admin'
    }
    client.get('/api/me', headers=admin_headers)

    # 1. Create Product
    product_data = {
        "codice": "BIO-KIWI-01",
        "descrizione": "Kiwi Hayward Bio",
        "categoria": "fresco",
        "unita_misura": "KG",
        "peso_netto": 1.0,
        "prezzo_vendita": 3.80,
        "prezzo_acquisto": 2.10,
        "aliquota_iva": 4,
        "in_scadenza": True
    }
    create_res = client.post('/api/products', json=product_data, headers=admin_headers)
    assert create_res.status_code == 201
    created_id = create_res.json()['id']

    # 2. Duplicate code rejected
    dup_res = client.post('/api/products', json=product_data, headers=admin_headers)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()['error']

    # 3. Get Products with filter
    list_res = client.get('/api/products?categoria=fresco', headers=admin_headers)
    assert list_res.status_code == 200
    products = list_res.json()
    assert any(p['codice'] == "BIO-KIWI-01" for p in products)

    # 4. Update Product
    update_res = client.put(f'/api/products/{created_id}', json={"prezzo_vendita": 4.20}, headers=admin_headers)
    assert update_res.status_code == 200
    assert update_res.json()['prezzo_vendita'] == 4.20

    # 5. Delete Product
    del_res = client.delete(f'/api/products/{created_id}', headers=admin_headers)
    assert del_res.status_code == 200

def test_api_rbac_partner_product(client, db_session):
    user_headers = {
        'X-Forwarded-Email': 'user@company.com'
    }
    client.get('/api/me', headers=user_headers)

    # Regular user attempting POST /api/partners -> 403
    p_res = client.post('/api/partners', json={"ragione_sociale": "Forbidden Partner"}, headers=user_headers)
    assert p_res.status_code == 403

    # Regular user attempting POST /api/products -> 403
    prod_res = client.post('/api/products', json={"codice": "FORBIDDEN", "descrizione": "Test"}, headers=user_headers)
    assert prod_res.status_code == 403
