import pytest
from services.barcode_label_service import BarcodeLabelService

def test_barcode_code128_svg_generation(db_session):
    svg = BarcodeLabelService.generate_code128_svg("BIO-ARAN-2026")
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert "<rect" in svg
    assert "BIO-ARAN-2026" in svg

def test_pallet_zpl_generation(db_session):
    data = {
        "descrizione": "Arance Tarocco Bio Sicilia",
        "codice_articolo": "BIO-ARAN-TRC",
        "lotto": "LOTTO-TRC-01",
        "data_scadenza": "2026-11-30",
        "colli": 48,
        "peso_netto": 480.0,
        "peso_lordo": 505.0,
        "tara": 25.0,
        "origine": "Italia - Sicilia",
        "ente_certificatore": "IT-BIO-009 CCPB"
    }
    zpl = BarcodeLabelService.generate_pallet_zpl(data)
    assert zpl.startswith("^XA")
    assert zpl.endswith("^XZ")
    assert "^BC" in zpl
    assert "Arance Tarocco Bio Sicilia" in zpl
    assert "LOTTO-TRC-01" in zpl
    assert "IT-BIO-009" in zpl

def test_collo_zpl_generation(db_session):
    data = {
        "descrizione": "Pere Abate Bio",
        "codice_articolo": "BIO-PERA-ABT",
        "lotto": "L-2026-09",
        "data_scadenza": "2026-10-31",
        "peso_netto": 10.0
    }
    zpl = BarcodeLabelService.generate_collo_zpl(data)
    assert zpl.startswith("^XA")
    assert zpl.endswith("^XZ")
    assert "Pere Abate Bio" in zpl
    assert "L-2026-09" in zpl

def test_html_preview_generation(db_session):
    data = {
        "descrizione": "Kiwi Hayward Bio",
        "codice_articolo": "BIO-KIWI-HAY",
        "lotto": "LOTTO-K-01",
        "data_scadenza": "2026-12-15",
        "colli": 30,
        "peso_netto": 300.0,
        "peso_lordo": 320.0,
        "origine": "Italia - Romagna",
        "ente_certificatore": "IT-BIO-009"
    }
    html_pallet = BarcodeLabelService.render_pallet_html(data)
    assert "Kiwi Hayward Bio" in html_pallet
    assert "LOTTO-K-01" in html_pallet
    assert "<svg" in html_pallet

    html_collo = BarcodeLabelService.render_collo_html(data)
    assert "Kiwi Hayward Bio" in html_collo
    assert "<svg" in html_collo

def test_api_labels_generate_endpoint(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    payload = {
        "label_type": "pallet",
        "descrizione": "Mele Gala Bio",
        "codice_articolo": "BIO-MELA-GALA",
        "lotto": "LOT-2026-001",
        "data_scadenza": "2026-11-20",
        "colli": 40,
        "peso_netto": 400.0,
        "peso_lordo": 425.0,
        "tara": 25.0,
        "origine": "Italia - Trentino",
        "ente_certificatore": "IT-BIO-009 CCPB"
    }

    res = client.post('/api/labels/generate', json=payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert "zpl" in data
    assert "^XA" in data["zpl"]
    assert "svg_barcode" in data
    assert "<svg" in data["svg_barcode"]
    assert "html_preview" in data
    assert "Mele Gala Bio" in data["html_preview"]

def test_api_delivery_note_labels_generation(client, db_session):
    from datetime import date
    from models import Partner, Product, DeliveryNote, DeliveryNoteItem, SystemEvent

    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    cli = Partner(ragione_sociale="Supermercati Bio SpA", tipo="cliente", nazione="IT")
    prod = Product(codice="BIO-ARAN-LBL", descrizione="Arance Bellarossa Bio", prezzo_vendita=2.0, in_scadenza=True)
    db_session.add_all([cli, prod])
    db_session.commit()

    ddt = DeliveryNote(
        numero=10,
        anno=2026,
        numero_completo="DDT-2026-0010",
        data_documento=date(2026, 10, 22),
        cliente_id=cli.id,
        colli_totali=50,
        peso_totale_netto=500.0,
        stato="confermato"
    )
    db_session.add(ddt)
    db_session.commit()

    item = DeliveryNoteItem(
        delivery_note_id=ddt.id,
        product_id=prod.id,
        descrizione=prod.descrizione,
        colli=50,
        quantita=500.0,
        prezzo_unitario=2.0,
        lotto="LOTTO-DDT-LBL",
        data_scadenza=date(2026, 11, 25)
    )
    db_session.add(item)
    db_session.commit()
    ddt_id = ddt.id

    res = client.get(f'/api/delivery-notes/{ddt_id}/labels', headers=admin_headers)
    assert res.status_code == 200
    labels_data = res.get_json()
    assert "labels" in labels_data
    assert len(labels_data["labels"]) == 1
    lbl = labels_data["labels"][0]
    assert "LOTTO-DDT-LBL" in lbl["zpl"]
    assert "<svg" in lbl["svg_barcode"]
    assert "Arance Bellarossa Bio" in lbl["html_preview"]

    # Check Event Bus emission
    ev = db_session.query(SystemEvent).filter_by(entita_tipo="delivery_note", entita_id=ddt_id).first()
    assert ev is not None
    assert ev.azione == "stampa_etichette_barcode"

def test_barcode_label_utf8_and_escaping(db_session):
    data = {
        "descrizione": "Pere Qualità Extra & Bio <1>",
        "codice_articolo": "BIO&PERA",
        "lotto": "L-2026/01",
        "peso_netto": "invalid_number"
    }
    zpl = BarcodeLabelService.generate_pallet_zpl(data)
    assert "^CI28" in zpl
    assert "Pere Qualità Extra & Bio <1>" in zpl

    svg = BarcodeLabelService.generate_code128_svg("BIO&PERA<1>")
    assert "BIO&amp;PERA&lt;1&gt;" in svg
