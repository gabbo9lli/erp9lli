import pytest
from datetime import datetime
from models import db, CustomerOrder, EcommerceSyncLog, Partner

def test_ecommerce_sync_models_persistence(client):
    with client.application.app_context():
        cli = Partner(ragione_sociale="Cliente Web", tipo="cliente")
        db.session.add(cli)
        db.session.commit()

        order = CustomerOrder(
            numero=1,
            anno=2026,
            numero_completo="ORD-2026-0001",
            cliente_id=cli.id,
            external_reference="SPREE-R999",
            canale_vendita="ecommerce"
        )
        db.session.add(order)
        db.session.commit()

        log = EcommerceSyncLog(
            tipo_operazione="import_order",
            external_order_id="SPREE-R999",
            customer_order_id=order.id,
            stato="success",
            payload_ricevuto={"number": "SPREE-R999", "total": 120.0}
        )
        db.session.add(log)
        db.session.commit()

        assert log.id is not None
        assert order.external_reference == "SPREE-R999"
        assert order.canale_vendita == "ecommerce"
        assert log.to_dict()["tipo_operazione"] == "import_order"

def test_ecommerce_service_import_order_and_idempotency(client):
    from services.ecommerce_service import EcommerceService
    from models import db, Product, CustomerOrder

    with client.application.app_context():
        p1 = Product(codice="BIO-ARAN-TRC", descrizione="Arance Tarocco Bio", prezzo_vendita=2.20)
        p2 = Product(codice="BIO-MELA-GLA", descrizione="Mele Gala Bio", prezzo_vendita=3.00)
        db.session.add_all([p1, p2])
        db.session.commit()

        payload = {
            "number": "R123456789",
            "email": "mario.rossi@bio.it",
            "bill_address": {
                "firstname": "Mario",
                "lastname": "Rossi",
                "address1": "Via Roma 10",
                "city": "Bologna",
                "zipcode": "40121"
            },
            "line_items": [
                {"sku": "BIO-ARAN-TRC", "quantity": 10, "price": 2.20},
                {"sku": "BIO-MELA-GLA", "quantity": 5, "price": 3.00}
            ]
        }

        # 1. First import: New order
        order, is_new = EcommerceService.process_incoming_order(payload)
        assert is_new is True
        assert order.id is not None
        assert order.external_reference == "R123456789"
        assert order.canale_vendita == "ecommerce"
        assert order.cliente.ragione_sociale == "Mario Rossi"
        assert order.cliente.pec == "mario.rossi@bio.it"
        assert len(order.items) == 2
        assert order.items[0].sequenza == 5
        assert order.items[1].sequenza == 10
        assert float(order.totale_imponibile) == 37.0

        # 2. Second import: Idempotent return existing
        order2, is_new2 = EcommerceService.process_incoming_order(payload)
        assert is_new2 is False
        assert order2.id == order.id
        assert CustomerOrder.query.filter_by(external_reference="R123456789").count() == 1

def test_ecommerce_service_stock_sync_feed(client):
    from services.ecommerce_service import EcommerceService
    from models import db, Product

    with client.application.app_context():
        p = Product(codice="BIO-LIMONE", descrizione="Limoni Bio Siracusa", prezzo_vendita=2.80)
        db.session.add(p)
        db.session.commit()

        feed = EcommerceService.get_stock_sync_feed()
        assert isinstance(feed, list)
        item = next((x for x in feed if x["sku"] == "BIO-LIMONE"), None)
        assert item is not None
        assert item["name"] == "Limoni Bio Siracusa"
        assert item["price"] == 2.80
        assert "stock" in item
        assert "in_stock" in item

def test_api_ecommerce_webhook_endpoint_auth_and_import(client):
    from models import db, Product, CustomerOrder, SystemEvent

    with client.application.app_context():
        p = Product(codice="BIO-ARAN-HOOK", descrizione="Arance Hook Bio", prezzo_vendita=2.50)
        db.session.add(p)
        db.session.commit()

    payload = {
        "number": "SPREE-HOOK-01",
        "email": "luigi.verdi@bio.it",
        "customer_name": "Luigi Verdi",
        "line_items": [
            {"sku": "BIO-ARAN-HOOK", "quantity": 4, "price": 2.50}
        ]
    }

    # 1. Invalid secret -> 401
    bad_res = client.post('/api/ecommerce/webhook/orders', json=payload, headers={"X-Ecommerce-Secret": "wrong-secret"})
    assert bad_res.status_code == 401

    # 2. Valid secret -> 201 Created
    headers = {"X-Ecommerce-Secret": "spree-secret-token"}
    res = client.post('/api/ecommerce/webhook/orders', json=payload, headers=headers)
    assert res.status_code == 201
    data = res.get_json()
    assert data["external_reference"] == "SPREE-HOOK-01"
    assert data["canale_vendita"] == "ecommerce"

    # 3. Second call with same payload -> 200 OK (idempotent)
    res_repeat = client.post('/api/ecommerce/webhook/orders', json=payload, headers=headers)
    assert res_repeat.status_code == 200
    assert res_repeat.get_json()["id"] == data["id"]

    # 4. Event Bus check
    with client.application.app_context():
        ev = SystemEvent.query.filter_by(entita_tipo="customer_order", entita_id=data["id"]).first()
        assert ev is not None
        assert ev.channel.codice == "WEBHOOK"

def test_api_ecommerce_stock_and_logs(client):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    # 1. Stock feed
    res_stock = client.get('/api/ecommerce/sync/stock', headers=admin_headers)
    assert res_stock.status_code == 200
    assert isinstance(res_stock.get_json(), list)

    # 2. Sync logs
    res_logs = client.get('/api/ecommerce/logs', headers=admin_headers)
    assert res_logs.status_code == 200
    assert isinstance(res_logs.get_json(), list)
