import pytest
from datetime import date
from models import db, Partner, Product, PurchaseDeliveryNote, PurchaseDeliveryNoteItem

def test_purchase_delivery_note_model(client):
    with client.application.app_context():
        supplier = Partner(ragione_sociale="BioProduttori Romagna", tipo="fornitore")
        prod = Product(codice="ART-BIO-CARICO", descrizione="Pesche Bio", in_scadenza=True, prezzo_acquisto=1.2)
        db.session.add_all([supplier, prod])
        db.session.commit()

        pdn = PurchaseDeliveryNote(
            numero_documento_fornitore="DDT-998/F",
            data_documento=date.today(),
            data_ricezione=date.today(),
            fornitore_id=supplier.id,
            colli_totali=10,
            peso_totale_netto=100.0,
            totale_imponibile=120.0
        )
        db.session.add(pdn)
        db.session.commit()

        item = PurchaseDeliveryNoteItem(
            purchase_delivery_note_id=pdn.id,
            product_id=prod.id,
            descrizione=prod.descrizione,
            colli=10,
            quantita=100.0,
            prezzo_unitario=1.2,
            lotto="LOTTO-PESCA-2026",
            data_scadenza=date.today()
        )
        db.session.add(item)
        db.session.commit()

        assert pdn.id is not None
        assert len(pdn.items) == 1
        assert pdn.numero_documento_fornitore == "DDT-998/F"

def test_create_purchase_validation_lotto_bio(client):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    with client.application.app_context():
        supplier = Partner(ragione_sociale="Fornitore Mele Bio", tipo="fornitore")
        prod = Product(codice="ART-MELE-SCAD", descrizione="Mele Bio con scadenza", in_scadenza=True, prezzo_acquisto=1.5)
        db.session.add_all([supplier, prod])
        db.session.commit()
        s_id, p_id = supplier.id, prod.id

    # 1. Missing lotto -> should return 400
    res_err1 = client.post('/api/purchases', json={
        "fornitore_id": s_id,
        "numero_documento_fornitore": "DDT-001/F",
        "items": [{"product_id": p_id, "colli": 10, "quantita": 100.0, "data_scadenza": "2026-11-20"}]
    }, headers=admin_headers)
    assert res_err1.status_code == 400
    assert "lotto" in res_err1.get_json()['error'].lower()

    # 2. Missing data_scadenza -> should return 400
    res_err2 = client.post('/api/purchases', json={
        "fornitore_id": s_id,
        "numero_documento_fornitore": "DDT-001/F",
        "items": [{"product_id": p_id, "colli": 10, "quantita": 100.0, "lotto": "LOTTO-TEST"}]
    }, headers=admin_headers)
    assert res_err2.status_code == 400
    assert "scadenza" in res_err2.get_json()['error'].lower()

    # 3. Valid purchase -> should return 201
    res_ok = client.post('/api/purchases', json={
        "fornitore_id": s_id,
        "numero_documento_fornitore": "DDT-001/F",
        "items": [{"product_id": p_id, "colli": 10, "quantita": 100.0, "prezzo_unitario": 1.5, "lotto": "LOTTO-TEST", "data_scadenza": "2026-11-20"}]
    }, headers=admin_headers)
    assert res_ok.status_code == 201
    data = res_ok.get_json()
    assert data['numero_documento_fornitore'] == "DDT-001/F"
    assert len(data['items']) == 1

def test_stock_running_calculation(client):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    with client.application.app_context():
        supplier = Partner(ragione_sociale="Fornitore Orto Bio", tipo="fornitore")
        customer = Partner(ragione_sociale="Cliente Orto Bio", tipo="cliente")
        prod = Product(codice="ART-KIWI-BIO", descrizione="Kiwi Bio", in_scadenza=True, prezzo_acquisto=2.0, prezzo_vendita=3.5)
        db.session.add_all([supplier, customer, prod])
        db.session.commit()
        s_id, c_id, p_id = supplier.id, customer.id, prod.id

    # 1. Carico fornitore 100 Kg LOTTO-KIWI-1
    client.post('/api/purchases', json={
        "fornitore_id": s_id,
        "numero_documento_fornitore": "DDT-FORN-1",
        "items": [{"product_id": p_id, "colli": 10, "quantita": 100.0, "lotto": "LOTTO-KIWI-1", "data_scadenza": "2026-11-30"}]
    }, headers=admin_headers)

    # 2. Scarico vendita DDT 30 Kg LOTTO-KIWI-1
    ddt_res = client.post('/api/delivery-notes', json={
        "cliente_id": c_id,
        "items": [{"product_id": p_id, "colli": 3, "quantita": 30.0, "lotto": "LOTTO-KIWI-1", "data_scadenza": "2026-11-30"}]
    }, headers=admin_headers)
    assert ddt_res.status_code == 201

    # 3. Check stock endpoint: giacenza deve essere esattamente 70 Kg
    stock_res = client.get('/api/warehouse/stock', headers=admin_headers)
    assert stock_res.status_code == 200
    stocks = stock_res.get_json()
    kiwi_stock = next((s for s in stocks if s['product_id'] == p_id and s['lotto'] == "LOTTO-KIWI-1"), None)
    assert kiwi_stock is not None
    assert kiwi_stock['giacenza_kg'] == 70.0
    assert kiwi_stock['colli_disponibili'] == 7

def test_fefo_suggestion_ordering(client):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    with client.application.app_context():
        supplier = Partner(ragione_sociale="Fornitore Arance", tipo="fornitore")
        prod = Product(codice="ART-ARAN-FEFO", descrizione="Arance Bio", in_scadenza=True, prezzo_acquisto=1.8)
        db.session.add_all([supplier, prod])
        db.session.commit()
        s_id, p_id = supplier.id, prod.id

    # Carico 1: Scadenza più lontana (25/11/2026)
    client.post('/api/purchases', json={
        "fornitore_id": s_id,
        "numero_documento_fornitore": "DDT-ARAN-LONTANA",
        "items": [{"product_id": p_id, "colli": 5, "quantita": 50.0, "lotto": "LOTTO-LONTANO", "data_scadenza": "2026-11-25"}]
    }, headers=admin_headers)

    # Carico 2: Scadenza più vicina (10/11/2026) -> DEVE USCIRE PRIMA (FEFO)!
    client.post('/api/purchases', json={
        "fornitore_id": s_id,
        "numero_documento_fornitore": "DDT-ARAN-VICINA",
        "items": [{"product_id": p_id, "colli": 5, "quantita": 50.0, "lotto": "LOTTO-VICINO", "data_scadenza": "2026-11-10"}]
    }, headers=admin_headers)

    # Richiesta suggerimento FEFO
    fefo_res = client.get(f'/api/warehouse/fefo-suggestions?product_id={p_id}', headers=admin_headers)
    assert fefo_res.status_code == 200
    suggestions = fefo_res.get_json()

    assert len(suggestions) == 2
    # Primo suggerimento deve essere LOTTO-VICINO (10/11/2026)
    assert suggestions[0]['lotto'] == "LOTTO-VICINO"
    assert suggestions[0]['data_scadenza'] == "2026-11-10"
    assert suggestions[0]['consigliato_fefo'] is True

    # Secondo suggerimento deve essere LOTTO-LONTANO (25/11/2026)
    assert suggestions[1]['lotto'] == "LOTTO-LONTANO"
    assert suggestions[1]['data_scadenza'] == "2026-11-25"
