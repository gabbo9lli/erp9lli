import pytest
from datetime import date
from models import Partner, Product, DeliveryNote, Invoice, InvoiceItem, InvoiceInstallment

def test_invoice_and_installment_models(client, db_session):
    p = Partner(ragione_sociale="Cliente Fattura Test", tipo="cliente")
    prod = Product(codice="ART-TEST", descrizione="Articolo Test", categoria="fresco", prezzo_vendita=10.0)
    db_session.add_all([p, prod])
    db_session.commit()

    inv = Invoice(
        numero=1,
        anno=2026,
        numero_completo="FT-2026-0001",
        tipo_documento="TD24",
        data_documento=date.today(),
        cliente_id=p.id,
        totale_imponibile=100.0,
        totale_imposta=4.0,
        totale_fattura=104.0,
        stato="emessa"
    )
    db_session.add(inv)
    db_session.commit()

    item = InvoiceItem(
        invoice_id=inv.id,
        product_id=prod.id,
        descrizione=prod.descrizione,
        colli=1,
        quantita=10.0,
        prezzo_unitario=10.0,
        imponibile_riga=100.0,
        aliquota_iva=4
    )
    inst = InvoiceInstallment(
        invoice_id=inv.id,
        numero_rata=1,
        totale_rate=1,
        data_scadenza=date.today(),
        importo=104.0,
        stato="aperta"
    )
    db_session.add_all([item, inst])
    db_session.commit()

    assert inv.id is not None
    assert len(inv.items) == 1
    assert len(inv.installments) == 1
    assert inv.numero_completo == "FT-2026-0001"

def test_unbilled_delivery_notes(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(ragione_sociale="Cliente Unbilled Test", tipo="cliente")
    prod = Product(codice="ART-UB", descrizione="Articolo Unbilled", prezzo_vendita=5.0)
    db_session.add_all([customer, prod])
    db_session.commit()
    c_id, p_id = customer.id, prod.id

    # Create DDT in bozza
    ddt_res = client.post('/api/delivery-notes', json={
        "cliente_id": c_id,
        "items": [{"product_id": p_id, "colli": 1, "quantita": 10.0}]
    }, headers=admin_headers)
    ddt_id = ddt_res.json()['id']

    # In bozza, should NOT be in unbilled list
    ub_res1 = client.get(f'/api/delivery-notes/unbilled?cliente_id={c_id}', headers=admin_headers)
    assert ub_res1.status_code == 200
    assert not any(d['id'] == ddt_id for d in ub_res1.json())

    # Confirm DDT -> Now it should appear in unbilled
    client.post(f'/api/delivery-notes/{ddt_id}/confirm', headers=admin_headers)
    ub_res2 = client.get(f'/api/delivery-notes/unbilled?cliente_id={c_id}', headers=admin_headers)
    assert any(d['id'] == ddt_id for d in ub_res2.json())

def test_invoice_differita_from_ddt(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(ragione_sociale="Bio Supermarket Differita", tipo="cliente", condizioni_pagamento="30/60gg fm")
    prod1 = Product(codice="ART-BIO-1", descrizione="Uva Bio", categoria="fresco", aliquota_iva=4, prezzo_vendita=2.0)
    prod2 = Product(codice="IMB-EPAL-1", descrizione="Pallet EPAL", categoria="imballo", aliquota_iva=22, prezzo_vendita=10.0)
    db_session.add_all([customer, prod1, prod2])
    db_session.commit()
    c_id, p1_id, p2_id = customer.id, prod1.id, prod2.id

    # Create and confirm DDT
    ddt_res = client.post('/api/delivery-notes', json={
        "cliente_id": c_id,
        "data_documento": "2026-10-20",
        "items": [
            {"product_id": p1_id, "colli": 10, "quantita": 100.0, "prezzo_unitario": 2.0},
            {"product_id": p2_id, "colli": 2, "quantita": 2.0, "prezzo_unitario": 10.0}
        ]
    }, headers=admin_headers)
    ddt_id = ddt_res.json()['id']
    client.post(f'/api/delivery-notes/{ddt_id}/confirm', headers=admin_headers)

    # Issue Differita Invoice
    inv_payload = {
        "cliente_id": c_id,
        "data_documento": "2026-10-31",
        "condizioni_pagamento": "30/60gg fm",
        "ddt_ids": [ddt_id]
    }
    inv_res = client.post('/api/invoices/from-ddt', json=inv_payload, headers=admin_headers)
    assert inv_res.status_code == 201
    inv_data = inv_res.json()

    assert inv_data['tipo_documento'] == "TD24"
    assert inv_data['numero_completo'] == "FT-2026-0001"
    assert inv_data['totale_imponibile'] == 220.0
    assert inv_data['totale_imposta'] == 12.4
    assert inv_data['totale_fattura'] == 232.4
    assert len(inv_data['items']) == 2
    assert inv_data['items'][0]['delivery_note_id'] == ddt_id

    # Castelletto IVA checks
    castelletto = inv_data['castelletto_iva']
    assert "4" in castelletto and castelletto["4"]["imposta"] == 8.0
    assert "22" in castelletto and castelletto["22"]["imposta"] == 4.4

    # Installments (2 rate for 30/60gg fm)
    rate = inv_data['installments']
    assert len(rate) == 2
    assert round(sum(r['importo'] for r in rate), 2) == 232.4

    # Check DDT transitioned to 'fatturato'
    from models import DeliveryNote
    ddt_db = db_session.get(DeliveryNote, ddt_id)
    assert ddt_db.stato == "fatturato"

def test_installments_quadratura_odd_amount(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(ragione_sociale="Cliente Rata Dispari", tipo="cliente", condizioni_pagamento="30/60gg fm")
    prod = Product(codice="ART-DISP", descrizione="Articolo Dispari", aliquota_iva=10, prezzo_vendita=90.95)
    db_session.add_all([customer, prod])
    db_session.commit()
    c_id, p_id = customer.id, prod.id

    # Direct invoice with odd total: 90.95 + 10% IVA (9.10) = 100.05
    payload = {
        "cliente_id": c_id,
        "condizioni_pagamento": "30/60gg fm",
        "items": [{"product_id": p_id, "colli": 1, "quantita": 1.0, "prezzo_unitario": 90.95, "aliquota_iva": 10}]
    }
    res = client.post('/api/invoices', json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data['totale_fattura'] == 100.05

    rate = data['installments']
    assert len(rate) == 2
    assert round(sum(r['importo'] for r in rate), 2) == 100.05

def test_pay_installment_and_auto_close_invoice(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(ragione_sociale="Cliente Pay Test", tipo="cliente", condizioni_pagamento="bonifico a vista")
    prod = Product(codice="ART-PAY", descrizione="Articolo Pay", prezzo_vendita=50.0, aliquota_iva=0)
    db_session.add_all([customer, prod])
    db_session.commit()
    c_id, p_id = customer.id, prod.id

    res = client.post('/api/invoices', json={
        "cliente_id": c_id,
        "condizioni_pagamento": "bonifico a vista",
        "items": [{"product_id": p_id, "colli": 1, "quantita": 1.0, "prezzo_unitario": 50.0, "aliquota_iva": 0}]
    }, headers=admin_headers)
    inv_data = res.json()
    inv_id = inv_data['id']
    rata_id = inv_data['installments'][0]['id']

    # Pay installment
    pay_res = client.post(f'/api/installments/{rata_id}/pay', headers=admin_headers)
    assert pay_res.status_code == 200
    assert pay_res.json()['stato'] == "incassata"

    # Check invoice status updated to 'saldata'
    inv_detail = client.get(f'/api/invoices/{inv_id}', headers=admin_headers).json()
    assert inv_detail['stato'] == "saldata"
