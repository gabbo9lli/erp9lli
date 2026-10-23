import pytest
from datetime import date, datetime
from models import Partner, Product, DeliveryNote, DeliveryNoteItem

def test_delivery_note_model_creation(client, db_session):
    client_p = Partner(ragione_sociale="Supermercato Bio", tipo="cliente")
    prod = Product(codice="BIO-PERA", descrizione="Pere Abate Bio", categoria="fresco", prezzo_vendita=3.20)
    db_session.add_all([client_p, prod])
    db_session.commit()

    ddt = DeliveryNote(
        numero=1,
        anno=2026,
        numero_completo="DDT-2026-0001",
        data_documento=date.today(),
        cliente_id=client_p.id,
        causale_trasporto="Vendita"
    )
    db_session.add(ddt)
    db_session.commit()

    item = DeliveryNoteItem(
        delivery_note_id=ddt.id,
        product_id=prod.id,
        descrizione=prod.descrizione,
        colli=10,
        quantita=100.0,
        prezzo_unitario=3.20
    )
    db_session.add(item)
    db_session.commit()

    assert ddt.id is not None
    assert len(ddt.items) == 1
    assert ddt.stato == "bozza"
    assert ddt.numero_completo == "DDT-2026-0001"

def test_create_delivery_note_with_items_and_totals(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(ragione_sociale="Coop Bio Nord", tipo="cliente")
    carrier = Partner(ragione_sociale="LD Trasporti", tipo="vettore")
    prod1 = Product(codice="ART-MELA", descrizione="Mele Bio", categoria="fresco", peso_netto=1.0, peso_lordo=1.05, prezzo_vendita=2.50, aliquota_iva=4, in_scadenza=False)
    prod2 = Product(codice="ART-PERA-2", descrizione="Pere Bio", categoria="fresco", peso_netto=1.0, peso_lordo=1.05, prezzo_vendita=3.00, aliquota_iva=4, in_scadenza=False)
    db_session.add_all([customer, carrier, prod1, prod2])
    db_session.commit()
    cust_id, carr_id, p1_id, p2_id = customer.id, carrier.id, prod1.id, prod2.id

    ddt_payload = {
        "cliente_id": cust_id,
        "vettore_id": carr_id,
        "causale_trasporto": "Vendita",
        "aspetto_beni": "Pallet",
        "porto": "Franco",
        "data_documento": "2026-10-20",
        "items": [
            {
                "product_id": p1_id,
                "descrizione": "Mele Bio Special",
                "colli": 10,
                "quantita": 100.0,
                "prezzo_unitario": 2.50
            },
            {
                "product_id": p2_id,
                "colli": 5,
                "quantita": 50.0,
                "prezzo_unitario": 3.00
            }
        ]
    }

    res = client.post('/api/delivery-notes', json=ddt_payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data['numero'] == 1
    assert data['numero_completo'] == "DDT-2026-0001"
    assert data['colli_totali'] == 15
    assert data['peso_totale_netto'] == 150.0
    assert data['totale_imponibile'] == 400.0  # (100 * 2.5) + (50 * 3.0)
    assert data['stato'] == "bozza"
    assert len(data['items']) == 2

def test_auto_numbering_sequential(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(ragione_sociale="Bio Market 2", tipo="cliente")
    prod = Product(codice="ART-KIWI", descrizione="Kiwi Bio", categoria="fresco", prezzo_vendita=4.0)
    db_session.add_all([customer, prod])
    db_session.commit()
    c_id, p_id = customer.id, prod.id

    payload = {
        "cliente_id": c_id,
        "data_documento": "2026-10-20",
        "items": [{"product_id": p_id, "colli": 2, "quantita": 20.0, "prezzo_unitario": 4.0}]
    }

    res1 = client.post('/api/delivery-notes', json=payload, headers=admin_headers)
    assert res1.status_code == 201
    n1 = res1.json()['numero']

    res2 = client.post('/api/delivery-notes', json=payload, headers=admin_headers)
    assert res2.status_code == 201
    n2 = res2.json()['numero']
    assert n2 == n1 + 1

def test_bio_traceability_validation(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(ragione_sociale="Cliente Bio Test", tipo="cliente")
    bio_prod = Product(codice="BIO-UVA", descrizione="Uva Bio Fresca", categoria="fresco", in_scadenza=True, prezzo_vendita=3.0)
    db_session.add_all([customer, bio_prod])
    db_session.commit()
    c_id, p_id = customer.id, bio_prod.id

    # 1. Missing lotto / scadenza -> Should fail with 400
    invalid_payload = {
        "cliente_id": c_id,
        "data_documento": "2026-10-20",
        "items": [{"product_id": p_id, "colli": 5, "quantita": 50.0}]
    }
    fail_res = client.post('/api/delivery-notes', json=invalid_payload, headers=admin_headers)
    assert fail_res.status_code == 400
    assert "lotto" in fail_res.json()['error'].lower()

    # 2. With lotto and scadenza -> Should succeed
    valid_payload = {
        "cliente_id": c_id,
        "data_documento": "2026-10-20",
        "items": [{
            "product_id": p_id,
            "colli": 5,
            "quantita": 50.0,
            "lotto": "L26-UVA-001",
            "data_scadenza": "2026-11-15"
        }]
    }
    ok_res = client.post('/api/delivery-notes', json=valid_payload, headers=admin_headers)
    assert ok_res.status_code == 201
    assert ok_res.json()['items'][0]['lotto'] == "L26-UVA-001"

def test_confirm_delivery_note_and_immutability(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(ragione_sociale="Cliente Immutabile", tipo="cliente")
    prod = Product(codice="ART-PASTA", descrizione="Pasta Bio", categoria="trasformato", prezzo_vendita=1.50)
    db_session.add_all([customer, prod])
    db_session.commit()
    c_id, p_id = customer.id, prod.id

    payload = {
        "cliente_id": c_id,
        "data_documento": "2026-10-20",
        "items": [{"product_id": p_id, "colli": 10, "quantita": 10.0, "prezzo_unitario": 1.50}]
    }
    create_res = client.post('/api/delivery-notes', json=payload, headers=admin_headers)
    ddt_id = create_res.json()['id']

    # Confirm DDT
    confirm_res = client.post(f'/api/delivery-notes/{ddt_id}/confirm', headers=admin_headers)
    assert confirm_res.status_code == 200
    assert confirm_res.json()['stato'] == "confermato"

    # Attempt to modify confirmed DDT -> should fail with 400
    modify_res = client.put(f'/api/delivery-notes/{ddt_id}', json={"note": "Modified note"}, headers=admin_headers)
    assert modify_res.status_code == 400
    assert "confermato" in modify_res.json()['error'].lower()

    # Attempt to delete confirmed DDT -> should fail with 400
    delete_res = client.delete(f'/api/delivery-notes/{ddt_id}', headers=admin_headers)
    assert delete_res.status_code == 400
