import pytest
from datetime import date
from models import Partner, Product, CustomerOrder, OrderItem

def test_get_modules_endpoint(client, db_session):
    res = client.get('/api/modules')
    assert res.status_code == 200
    data = res.json()
    assert "anagrafiche" in data
    assert "orders" in data
    assert "delivery_notes" in data
    assert "invoicing" in data
    assert "accounting" in data
    assert data["anagrafiche"] is True

def test_order_model_persistence_and_residual(client, db_session):
    p = Partner(ragione_sociale="Cliente Ordine Test", tipo="cliente")
    prod = Product(codice="ART-ORD-1", descrizione="Mele Bio", prezzo_vendita=2.5)
    db_session.add_all([p, prod])
    db_session.commit()

    order = CustomerOrder(
        numero=1,
        anno=2026,
        numero_completo="ORD-2026-0001",
        data_ordine=date.today(),
        cliente_id=p.id,
        stato="aperto"
    )
    db_session.add(order)
    db_session.commit()

    item = OrderItem(
        order_id=order.id,
        product_id=prod.id,
        sequenza=5,
        descrizione=prod.descrizione,
        colli_ordinati=10,
        quantita_ordinata=100.0,
        colli_consegnati=4,
        quantita_consegnata=40.0,
        prezzo_unitario=2.5
    )
    db_session.add(item)
    db_session.commit()

    assert order.id is not None
    assert len(order.items) == 1
    assert item.quantita_residua == 60.0

def test_create_order_with_step5_sequences(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(ragione_sociale="Supermercato Bio Ordini", tipo="cliente")
    prod1 = Product(codice="ART-MELE", descrizione="Mele Golden Bio", prezzo_vendita=2.5)
    prod2 = Product(codice="ART-PERE", descrizione="Pere Abate Bio", prezzo_vendita=3.0)
    db_session.add_all([customer, prod1, prod2])
    db_session.commit()
    c_id, p1_id, p2_id = customer.id, prod1.id, prod2.id

    payload = {
        "cliente_id": c_id,
        "data_richiesta": "2026-10-25",
        "items": [
            {"product_id": p1_id, "colli_ordinati": 10, "quantita_ordinata": 100.0, "prezzo_unitario": 2.5},
            {"product_id": p2_id, "colli_ordinati": 5, "quantita_ordinata": 50.0, "prezzo_unitario": 3.0}
        ]
    }
    res = client.post('/api/orders', json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()

    assert data['numero_completo'] == f"ORD-{date.today().year}-0001"
    assert data['stato'] == "aperto"
    assert data['totale_imponibile'] == 400.0
    assert len(data['items']) == 2
    assert data['items'][0]['sequenza'] == 5
    assert data['items'][1]['sequenza'] == 10
    assert data['items'][0]['quantita_residua'] == 100.0

def test_order_partial_and_full_fulfillment_to_ddt(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(ragione_sociale="Natura Bio Marche", tipo="cliente")
    prod = Product(codice="ART-CAROTE", descrizione="Carote Bio", aliquota_iva=4, prezzo_vendita=1.8)
    db_session.add_all([customer, prod])
    db_session.commit()
    c_id, p_id = customer.id, prod.id

    # Create order of 100 Kg
    order_res = client.post('/api/orders', json={
        "cliente_id": c_id,
        "items": [{"product_id": p_id, "colli_ordinati": 10, "quantita_ordinata": 100.0, "prezzo_unitario": 1.8}]
    }, headers=admin_headers)
    order_data = order_res.json()
    order_id = order_data['id']
    item_id = order_data['items'][0]['id']

    # Fulfill partially: 40 Kg out of 100 Kg
    partial_payload = {
        "items": [{"order_item_id": item_id, "colli": 4, "quantita": 40.0}]
    }
    ful_res1 = client.post(f'/api/orders/{order_id}/fulfill-to-ddt', json=partial_payload, headers=admin_headers)
    assert ful_res1.status_code == 201
    ful_data1 = ful_res1.json()

    assert "ddt" in ful_data1
    assert "order" in ful_data1
    assert ful_data1['ddt']['numero_completo'].startswith('DDT-')
    assert ful_data1['order']['stato'] == "in_lavorazione"
    assert ful_data1['order']['items'][0]['quantita_consegnata'] == 40.0
    assert ful_data1['order']['items'][0]['quantita_residua'] == 60.0

    # Fulfill the rest: 60 Kg
    full_payload = {
        "items": [{"order_item_id": item_id, "colli": 6, "quantita": 60.0}]
    }
    ful_res2 = client.post(f'/api/orders/{order_id}/fulfill-to-ddt', json=full_payload, headers=admin_headers)
    assert ful_res2.status_code == 201
    ful_data2 = ful_res2.json()

    assert ful_data2['order']['stato'] == "chiuso"
    assert ful_data2['order']['items'][0]['quantita_consegnata'] == 100.0
    assert ful_data2['order']['items'][0]['quantita_residua'] == 0.0
    assert ful_data2['order']['items'][0]['stato'] == "chiuso"

def test_order_service_direct_fulfillment_dispatches_event(db_session):
    from services.order_service import OrderService
    from models import Partner, Product, SystemEvent

    cli = Partner(ragione_sociale="Cliente Event Test", tipo="cliente")
    prod = Product(codice="EVT-01", descrizione="Prodotto Evento", prezzo_vendita=5.0)
    db_session.add_all([cli, prod])
    db_session.commit()

    order = OrderService.create_order(db_session, {
        "cliente_id": cli.id,
        "items": [{"product_id": prod.id, "colli_ordinati": 2, "quantita_ordinata": 20.0, "prezzo_unitario": 5.0}]
    })

    ddt, updated_order = OrderService.fulfill_to_ddt(db_session, order.id, {})
    assert ddt is not None
    assert updated_order.stato == "chiuso"

    ev = db_session.query(SystemEvent).filter_by(entita_tipo="order", entita_id=order.id).first()
    assert ev is not None
    assert ev.azione == "evasione_ordine"

