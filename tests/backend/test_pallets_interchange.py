import pytest
from datetime import date, timedelta
from models import db, Partner, PalletType, PalletReceipt, PalletReceiptItem

def test_pallet_models_persistence(client):
    with client.application.app_context():
        partner = Partner(ragione_sociale="Cliente Pallet Test", tipo="cliente")
        ptype = PalletType(codice="EPAL", descrizione="Pallet EUR/EPAL Legno Standard", valore_risarcimento=18.0)
        db.session.add_all([partner, ptype])
        db.session.commit()

        receipt = PalletReceipt(
            numero=1,
            anno=2026,
            numero_completo="BP-2026-0001",
            data_emissione=date.today(),
            data_limite_restituzione=date.today() + timedelta(days=60),
            partner_id=partner.id,
            tipo="uscita",
            totale_consegnati=15,
            totale_restituiti=0,
            saldo_netto=15,
            stato="aperto"
        )
        db.session.add(receipt)
        db.session.commit()

        item = PalletReceiptItem(
            pallet_receipt_id=receipt.id,
            pallet_type_id=ptype.id,
            quantita_consegnata=15,
            quantita_restituita=0,
            saldo_riga=15
        )
        db.session.add(item)
        db.session.commit()

        assert receipt.id is not None
        assert len(receipt.items) == 1
        assert receipt.saldo_netto == 15
        assert receipt.numero_completo == "BP-2026-0001"

def test_create_pallet_receipt_sequential_and_term(client):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    with client.application.app_context():
        customer = Partner(ragione_sociale="Supermercati Bio Pallet", tipo="cliente")
        ptype = PalletType(codice="EPAL", descrizione="EUR/EPAL Standard", valore_risarcimento=18.0)
        db.session.add_all([customer, ptype])
        db.session.commit()
        c_id, pt_id = customer.id, ptype.id

    payload = {
        "partner_id": c_id,
        "tipo": "uscita",
        "items": [
            {"pallet_type_id": pt_id, "quantita_consegnata": 20, "quantita_restituita": 5}
        ]
    }
    res = client.post('/api/pallets/receipts', json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.get_json()

    assert data['numero_completo'] == f"BP-{date.today().year}-0001"
    assert data['totale_consegnati'] == 20
    assert data['totale_restituiti'] == 5
    assert data['saldo_netto'] == 15
    assert data['stato'] == "aperto"
    expected_term = (date.today() + timedelta(days=60)).isoformat()
    assert data['data_limite_restituzione'] == expected_term

def test_pallet_receipt_return_and_settlement(client):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    with client.application.app_context():
        vettore = Partner(ragione_sociale="Trasporti Rapidi Bio", tipo="vettore")
        ptype = PalletType(codice="CPR_40x60", descrizione="Cassa CPR", valore_risarcimento=2.5)
        db.session.add_all([vettore, ptype])
        db.session.commit()
        v_id, pt_id = vettore.id, ptype.id

    # Create receipt with 30 pallets out, 0 in -> balance 30
    res_b = client.post('/api/pallets/receipts', json={
        "partner_id": v_id,
        "items": [{"pallet_type_id": pt_id, "quantita_consegnata": 30, "quantita_restituita": 0}]
    }, headers=admin_headers)
    receipt_id = res_b.get_json()['id']

    # 1. Partial return: return 10 pallets -> balance becomes 20
    ret_res1 = client.post(f'/api/pallets/receipts/{receipt_id}/return', json={
        "items": [{"pallet_type_id": pt_id, "quantita_restituita": 10}]
    }, headers=admin_headers)
    assert ret_res1.status_code == 200
    data1 = ret_res1.get_json()
    assert data1['saldo_netto'] == 20
    assert data1['stato'] == "aperto"

    # 2. Complete return: return remaining 20 pallets -> balance becomes 0, status 'saldato'
    ret_res2 = client.post(f'/api/pallets/receipts/{receipt_id}/return', json={
        "items": [{"pallet_type_id": pt_id, "quantita_restituita": 20}]
    }, headers=admin_headers)
    assert ret_res2.status_code == 200
    data2 = ret_res2.get_json()
    assert data2['saldo_netto'] == 0
    assert data2['stato'] == "saldato"

def test_pallet_ledger_balances(client):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    with client.application.app_context():
        customer = Partner(ragione_sociale="Supermercati Bio Pallet", tipo="cliente")
        ptype = PalletType(codice="EPAL", descrizione="EUR/EPAL Standard", valore_risarcimento=18.0)
        db.session.add_all([customer, ptype])
        db.session.commit()
        c_id, pt_id = customer.id, ptype.id

    client.post('/api/pallets/receipts', json={
        "partner_id": c_id,
        "items": [{"pallet_type_id": pt_id, "quantita_consegnata": 20, "quantita_restituita": 5}]
    }, headers=admin_headers)

    res = client.get('/api/pallets/ledger', headers=admin_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    customer_ledger = next((l for l in data if l['partner_nome'] == "Supermercati Bio Pallet"), None)
    assert customer_ledger is not None
    assert customer_ledger['saldi']['EPAL'] == 15

def test_invoice_unreturned_pallets_reverse_charge(client):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    with client.application.app_context():
        customer = Partner(ragione_sociale="Cliente Inadempiente Pallet", tipo="cliente")
        ptype = PalletType(codice="EPAL", descrizione="EUR/EPAL Standard", valore_risarcimento=18.0)
        db.session.add_all([customer, ptype])
        db.session.commit()
        c_id, pt_id = customer.id, ptype.id

    # Create unreturned receipt: 10 EPAL at 18€ = 180€
    res_b = client.post('/api/pallets/receipts', json={
        "partner_id": c_id,
        "items": [{"pallet_type_id": pt_id, "quantita_consegnata": 10, "quantita_restituita": 0}]
    }, headers=admin_headers)
    receipt_id = res_b.get_json()['id']

    # Invoice for unreturned pallets
    inv_res = client.post(f'/api/pallets/receipts/{receipt_id}/invoice-unreturned', headers=admin_headers)
    assert inv_res.status_code == 201
    inv_data = inv_res.get_json()

    assert inv_data['tipo_documento'] == "TD01"
    assert inv_data['totale_imponibile'] == 180.0
    assert inv_data['totale_imposta'] == 0.0
    assert inv_data['totale_fattura'] == 180.0
    assert "Reverse Charge" in inv_data['note']
    assert "182/2025" in inv_data['note']

    # Receipt status updated to 'fatturato'
    rec_detail = client.get(f'/api/pallets/receipts/{receipt_id}', headers=admin_headers).get_json()
    assert rec_detail['stato'] == "fatturato"
