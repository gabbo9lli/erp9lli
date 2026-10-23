import pytest
from datetime import date
from models import Partner, Product, CmrDocument, CmrItem

def test_cmr_models_persistence(client, db_session):
    dest = Partner(ragione_sociale="Bio c' Bon Bruxelles", nazione="BE", tipo="cliente")
    vett = Partner(ragione_sociale="LD Trasporti Srl", nazione="IT", tipo="vettore")
    db_session.add_all([dest, vett])
    db_session.commit()

    cmr = CmrDocument(
        numero=1,
        anno=2026,
        numero_completo="CMR-2026-0001",
        data_documento=date.today(),
        cliente_id=dest.id,
        vettore_id=vett.id,
        luogo_carico="ALESSANDRIA (AL)",
        luogo_consegna="Rue de la Loi 15, Bruxelles (BE)",
        targa_automezzo="FX982KJ",
        targa_rimorchio="XA112LL",
        totale_colli=50,
        peso_totale_netto=500.0,
        peso_totale_lordo=525.0
    )
    db_session.add(cmr)
    db_session.commit()

    item = CmrItem(
        cmr_document_id=cmr.id,
        riga_numero=1,
        contrassegno_lotto="LOTTO-BIO-2026",
        numero_colli=50,
        modo_imballaggio="Casse su Pallet EPAL",
        natura_merce="Arance Tarocco Biologiche",
        codice_nc="08051020",
        peso_netto_kg=500.0,
        peso_lordo_kg=525.0
    )
    db_session.add(item)
    db_session.commit()

    assert cmr.id is not None
    assert len(cmr.items) == 1
    assert cmr.numero_completo == "CMR-2026-0001"

def test_create_cmr_from_ddt_with_alessandria_hub(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    dest = Partner(ragione_sociale="Bio c' Bon Bruxelles", nazione="BE", citta="Bruxelles", indirizzo="Rue de la Loi 15", tipo="cliente")
    vett = Partner(ragione_sociale="LD Trasporti Srl", nazione="IT", tipo="vettore")
    prod = Product(codice="ART-BIO-EXP", descrizione="Arance Bio Export", codice_nc="08051020", prezzo_vendita=2.5)
    db_session.add_all([dest, vett, prod])
    db_session.commit()
    d_id, v_id, p_id = dest.id, vett.id, prod.id

    # Create DDT for foreign client with LD Trasporti
    ddt_res = client.post('/api/delivery-notes', json={
        "cliente_id": d_id,
        "vettore_id": v_id,
        "items": [{"product_id": p_id, "colli": 40, "quantita": 400.0, "lotto": "LOTTO-BE-1"}]
    }, headers=admin_headers)
    assert ddt_res.status_code == 201
    ddt_id = ddt_res.json()['id']

    # Generate CMR from DDT
    cmr_res = client.post(f'/api/cmr/from-ddt/{ddt_id}', headers=admin_headers)
    assert cmr_res.status_code == 201
    cmr_data = cmr_res.json()

    assert cmr_data['numero_completo'] == f"CMR-{date.today().year}-0001"
    assert cmr_data['cliente_id'] == d_id
    assert cmr_data['vettore_id'] == v_id
    assert cmr_data['luogo_carico'] == "ALESSANDRIA (AL)"
    assert "Bruxelles" in cmr_data['luogo_consegna']
    assert cmr_data['totale_colli'] == 40
    assert cmr_data['peso_totale_netto'] == 400.0
    assert cmr_data['ha_allegato_righe'] is False

def test_cmr_21_rows_rule_and_attachment_flag(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    dest = Partner(ragione_sociale="Bio Markt Munchen", nazione="DE", citta="Munchen", tipo="cliente")
    prod = Product(codice="ART-GEN", descrizione="Ortaggio Bio", prezzo_vendita=1.0)
    db_session.add_all([dest, prod])
    db_session.commit()
    d_id, p_id = dest.id, prod.id

    items_25 = [
        {"natura_merce": f"Articolo {i}", "numero_colli": 2, "peso_netto_kg": 20.0, "peso_lordo_kg": 21.0}
        for i in range(1, 26)
    ]
    cmr_res = client.post('/api/cmr', json={
        "cliente_id": d_id,
        "luogo_consegna": "Munchen (DE)",
        "items": items_25
    }, headers=admin_headers)
    assert cmr_res.status_code == 201
    cmr_data = cmr_res.json()

    assert len(cmr_data['items']) == 25
    assert cmr_data['ha_allegato_righe'] is True

def test_cmr_print_format_boxes(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    dest = Partner(ragione_sociale="Bio Shop Paris", nazione="FR", citta="Paris", indirizzo="Rue de Rivoli", tipo="cliente")
    db_session.add(dest)
    db_session.commit()
    d_id = dest.id

    res = client.post('/api/cmr', json={
        "cliente_id": d_id,
        "luogo_consegna": "Paris (FR)",
        "targa_automezzo": "AB123CD",
        "targa_rimorchio": "EF456GH",
        "items": [{"natura_merce": "Vino Bio", "numero_colli": 10, "peso_netto_kg": 60.0, "peso_lordo_kg": 65.0}]
    }, headers=admin_headers)
    cmr_id = res.json()['id']

    print_res = client.get(f'/api/cmr/{cmr_id}/print', headers=admin_headers)
    assert print_res.status_code == 200
    boxes = print_res.json()

    assert "casella_1_mittente" in boxes
    assert "casella_2_destinatario" in boxes
    assert "casella_3_luogo_consegna" in boxes
    assert "casella_4_luogo_carico" in boxes
    assert "casella_16_trasportatore" in boxes
    assert "caselle_merci" in boxes
    assert boxes["casella_2_destinatario"]["ragione_sociale"] == "Bio Shop Paris"
