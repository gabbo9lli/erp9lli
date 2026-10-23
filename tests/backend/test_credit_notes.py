import pytest
from datetime import date
from models import Partner, Product, Invoice, InvoiceItem, InvoiceInstallment

def test_credit_note_model_persistence(client, db_session):
    customer = Partner(ragione_sociale="Cliente NC Test", tipo="cliente")
    db_session.add(customer)
    db_session.commit()

    inv = Invoice(
        numero=1, anno=2026, numero_completo="FT-2026-0001",
        tipo_documento="TD24", data_documento=date.today(),
        cliente_id=customer.id, totale_imponibile=100.0,
        totale_imposta=4.0, totale_fattura=104.0
    )
    db_session.add(inv)
    db_session.commit()

    nc = Invoice(
        numero=1, anno=2026, numero_completo="NC-2026-0001",
        tipo_documento="TD04", data_documento=date.today(),
        cliente_id=customer.id, totale_imponibile=50.0,
        totale_imposta=2.0, totale_fattura=52.0,
        invoice_origine_id=inv.id, invoice_origine_numero=inv.numero_completo,
        causale_storno="Reso parziale merce avariata",
        reintegro_magazzino=False
    )
    db_session.add(nc)
    db_session.commit()

    assert nc.id is not None
    assert nc.invoice_origine_id == inv.id
    assert nc.tipo_documento == "TD04"
    assert nc.numero_completo == "NC-2026-0001"

def test_create_credit_note_partial_reversal_and_installments_compensation(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(ragione_sociale="Supermercati Bio Italia SpA", partita_iva="01234567890", tipo="cliente")
    prod = Product(codice="BIO-ARAN", descrizione="Arance Bio", prezzo_vendita=2.0)
    db_session.add_all([customer, prod])
    db_session.commit()
    c_id, p_id = customer.id, prod.id

    inv_res = client.post('/api/invoices', json={
        "cliente_id": c_id,
        "tipo_documento": "TD01",
        "condizioni_pagamento": "30gg fm",
        "items": [{"product_id": p_id, "quantita": 100, "prezzo_unitario": 2.0, "aliquota_iva": 4}]
    }, headers=admin_headers)
    assert inv_res.status_code == 201
    inv_id = inv_res.get_json()['id']

    inv_detail = client.get(f'/api/invoices/{inv_id}', headers=admin_headers).get_json()
    assert inv_detail['totale_fattura'] == 208.0
    item_id = inv_detail['items'][0]['id']

    nc_res = client.post(f'/api/invoices/{inv_id}/credit-note', json={
        "causale_storno": "Storno per 20 kg arance danneggiate",
        "compensa_scadenzario": True,
        "reintegro_magazzino": False,
        "items": [
            {"invoice_item_id": item_id, "quantita_stornata": 20.0}
        ]
    }, headers=admin_headers)
    assert nc_res.status_code == 201
    nc_data = nc_res.get_json()

    assert nc_data['tipo_documento'] == "TD04"
    assert nc_data['numero_completo'] == f"NC-{date.today().year}-0001"
    assert nc_data['totale_imponibile'] == 40.0
    assert nc_data['totale_imposta'] == 1.60
    assert nc_data['totale_fattura'] == 41.60
    assert nc_data['invoice_origine_id'] == inv_id

    inv_updated = client.get(f'/api/invoices/{inv_id}', headers=admin_headers).get_json()
    assert inv_updated['installments'][0]['importo'] == 166.40
    assert inv_updated['installments'][0]['stato'] == "aperta"

def test_credit_note_full_compensation_closes_invoice(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(ragione_sociale="Cliente Storno Totale", tipo="cliente")
    prod = Product(codice="BIO-LIM", descrizione="Limoni Bio", prezzo_vendita=3.0)
    db_session.add_all([customer, prod])
    db_session.commit()
    c_id, p_id = customer.id, prod.id

    inv_res = client.post('/api/invoices', json={
        "cliente_id": c_id,
        "tipo_documento": "TD01",
        "items": [{"product_id": p_id, "quantita": 10, "prezzo_unitario": 3.0, "aliquota_iva": 4}]
    }, headers=admin_headers)
    inv_data = inv_res.get_json()
    inv_id = inv_data['id']
    item_id = inv_data['items'][0]['id']

    nc_res = client.post(f'/api/invoices/{inv_id}/credit-note', json={
        "causale_storno": "Annullamento totale ordine errato",
        "compensa_scadenzario": True,
        "items": [{"invoice_item_id": item_id, "quantita_stornata": 10.0}]
    }, headers=admin_headers)
    assert nc_res.status_code == 201

    inv_updated = client.get(f'/api/invoices/{inv_id}', headers=admin_headers).get_json()
    assert inv_updated['installments'][0]['importo'] == 0.0
    assert inv_updated['installments'][0]['stato'] == "incassata"
    assert inv_updated['stato'] == "saldata"

def test_credit_note_sdi_xml_with_dati_fatture_collegate(client, db_session):
    from services.sdi_service import generate_sdi_xml
    import xml.etree.ElementTree as ET

    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(
        ragione_sociale="Bio Supermarket Roma",
        partita_iva="05566778899",
        codice_sdi="M5UXCR1",
        cap="00185",
        citta="Roma",
        nazione="IT",
        tipo="cliente"
    )
    prod = Product(codice="ART-MELE", descrizione="Mele Bio", prezzo_vendita=2.0)
    db_session.add_all([customer, prod])
    db_session.commit()
    c_id, p_id = customer.id, prod.id

    inv_res = client.post('/api/invoices', json={
        "cliente_id": c_id,
        "tipo_documento": "TD01",
        "items": [{"product_id": p_id, "quantita": 50, "prezzo_unitario": 2.0, "aliquota_iva": 4}]
    }, headers=admin_headers)
    inv_id = inv_res.get_json()['id']
    inv_num = inv_res.get_json()['numero_completo']
    item_id = inv_res.get_json()['items'][0]['id']

    nc_res = client.post(f'/api/invoices/{inv_id}/credit-note', json={
        "causale_storno": "Rettifica prezzo concordata",
        "items": [{"invoice_item_id": item_id, "quantita_stornata": 10.0}]
    }, headers=admin_headers)
    nc_id = nc_res.get_json()['id']

    nc_obj = db_session.get(Invoice, nc_id)
    xml_str, filename = generate_sdi_xml(nc_obj)

    root = ET.fromstring(xml_str)
    assert root.find("FatturaElettronicaBody/DatiGenerali/DatiGeneraliDocumento/TipoDocumento").text == "TD04"
    collegate = root.find("FatturaElettronicaBody/DatiGenerali/DatiFattureCollegate")
    assert collegate is not None
    assert collegate.find("IdDocumento").text == inv_num
