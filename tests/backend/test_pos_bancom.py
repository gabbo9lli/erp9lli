import pytest
from datetime import datetime, date
from models import db, PosStation, PosSale, PosSaleItem, Product

def test_pos_models_persistence(client):
    with client.application.app_context():
        station = PosStation(
            codice="CASSA_01",
            nome="Cassa Banco Principale",
            driver_tipo="simulator",
            matricola_rt="99MEY123456",
            intestazione="ReteBio Società Agricola\nVia della Spiga 1, Bologna",
            pie_pagina="Arrivederci e grazie!"
        )
        db.session.add(station)
        db.session.commit()

        p = Product(codice="BIO-MELA", descrizione="Mela Bio", prezzo_vendita=2.50, aliquota_iva=4)
        db.session.add(p)
        db.session.commit()

        sale = PosSale(
            pos_station_id=station.id,
            numero_scontrino="SC-2026-0001",
            totale_lordo=5.00,
            totale_imponibile=4.81,
            totale_iva=0.19,
            metodo_pagamento="contanti",
            importo_pagato=10.00,
            importo_resto=5.00
        )
        db.session.add(sale)
        db.session.commit()

        item = PosSaleItem(
            pos_sale_id=sale.id,
            product_id=p.id,
            quantita=2.0,
            prezzo_unitario=2.50,
            aliquota_iva=4.0,
            subtotale=5.00
        )
        db.session.add(item)
        db.session.commit()

        assert sale.id is not None
        assert len(sale.items) == 1
        assert sale.station.codice == "CASSA_01"
        assert sale.to_dict()["numero_scontrino"] == "SC-2026-0001"

def test_pos_driver_simulator_output(client):
    from services.pos_driver_service import PosDriverService
    from models import db, PosStation, PosSale, PosSaleItem, Product

    with client.application.app_context():
        station = PosStation(
            codice="CASSA_SIM",
            nome="Cassa Banco Simulatore",
            driver_tipo="simulator",
            matricola_rt="99MEY999999",
            intestazione="RETEBIO SOCIETA' AGRICOLA\nBOLOGNA (BO)",
            pie_pagina="ARRIVEDERCI E GRAZIE"
        )
        db.session.add(station)
        p = Product(codice="BIO-PERA", descrizione="Pera Bio Abate", prezzo_vendita=3.20, aliquota_iva=4)
        db.session.add(p)
        db.session.commit()

        sale = PosSale(
            pos_station_id=station.id,
            numero_scontrino="SC-2026-0002",
            totale_lordo=6.40,
            totale_imponibile=6.15,
            totale_iva=0.25,
            metodo_pagamento="contanti",
            importo_pagato=10.00,
            importo_resto=3.60
        )
        db.session.add(sale)
        db.session.commit()

        item = PosSaleItem(
            pos_sale_id=sale.id,
            product_id=p.id,
            quantita=2.0,
            prezzo_unitario=3.20,
            aliquota_iva=4.0,
            subtotale=6.40,
            lotto="L-PERA-2026",
            data_scadenza=date(2026, 11, 15)
        )
        db.session.add(item)
        db.session.commit()

        result = PosDriverService.print_ticket(sale, station)
        assert result["success"] is True
        assert result["stato_fiscale"] == "simulato"
        ticket = result["ticket_ascii"]
        assert "RETEBIO SOCIETA' AGRICOLA" in ticket
        assert "SC-2026-0002" in ticket
        assert "Pera Bio Abate" in ticket
        assert "L-PERA-2026" in ticket
        assert "6.40" in ticket
        assert "CONTANTI" in ticket
        assert "3.60" in ticket
        assert "99MEY999999" in ticket
        assert "ARRIVEDERCI E GRAZIE" in ticket

def test_api_create_pos_sale_with_fefo_and_accounting(client):
    from models import db, Partner, Product, PurchaseDeliveryNote, PurchaseDeliveryNoteItem, PosStation, PosSale, JournalEntry
    from seed_accounting import seed_chart_of_accounts

    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    with client.application.app_context():
        seed_chart_of_accounts()

        # Seed supplier and purchase note with 2 lots
        forn = Partner(ragione_sociale="Fornitore Bio Srl", tipo="fornitore", partita_iva="12345678901")
        db.session.add(forn)
        db.session.commit()

        p = Product(codice="BIO-KIWI", descrizione="Kiwi Bio Hayward", prezzo_vendita=2.50, aliquota_iva=4, in_scadenza=True)
        db.session.add(p)
        db.session.commit()

        p_note = PurchaseDeliveryNote(numero_documento_fornitore="DDT-ACQ-01", data_documento=date(2026, 10, 1), fornitore_id=forn.id)
        db.session.add(p_note)
        db.session.commit()

        item_a = PurchaseDeliveryNoteItem(purchase_delivery_note_id=p_note.id, product_id=p.id, descrizione=p.descrizione, quantita=10.0, prezzo_unitario=1.0, lotto="LOTTO-EARLY", data_scadenza=date(2026, 10, 30))
        item_b = PurchaseDeliveryNoteItem(purchase_delivery_note_id=p_note.id, product_id=p.id, descrizione=p.descrizione, quantita=20.0, prezzo_unitario=1.0, lotto="LOTTO-LATE", data_scadenza=date(2026, 12, 31))
        db.session.add_all([item_a, item_b])
        db.session.commit()

        station = PosStation(codice="CASSA_01", nome="Cassa Principale", driver_tipo="simulator", matricola_rt="99MEY0001")
        db.session.add(station)
        db.session.commit()
        st_id = station.id
        p_id = p.id

    payload = {
        "pos_station_id": st_id,
        "metodo_pagamento": "contanti",
        "importo_pagato": 20.00,
        "items": [
            {
                "product_id": p_id,
                "quantita": 3.0,
                "prezzo_unitario": 2.50
            }
        ]
    }

    res = client.post('/api/pos/sales', json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.get_json()
    assert data["totale_lordo"] == 7.50
    assert data["importo_resto"] == 12.50
    assert data["numero_scontrino"].startswith("SC-")
    assert len(data["items"]) == 1
    # FEFO should have automatically assigned LOTTO-EARLY!
    assert data["items"][0]["lotto"] == "LOTTO-EARLY"
    assert "ticket_ascii" in data
    assert "SC-" in data["ticket_ascii"]
    assert "LOTTO-EARLY" in data["ticket_ascii"]

    with client.application.app_context():
        sale = db.session.get(PosSale, data["id"])
        assert sale.journal_entry_id is not None
        je = db.session.get(JournalEntry, sale.journal_entry_id)
        assert je is not None
        assert abs(float(je.totale_dare) - float(je.totale_avere)) <= 0.001

def test_api_pos_sale_insufficient_payment_rejected(client):
    from models import db, PosStation, Product

    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    with client.application.app_context():
        station = PosStation.query.filter_by(codice="CASSA_01").first()
        if not station:
            station = PosStation(codice="CASSA_01", nome="Cassa Principale", driver_tipo="simulator")
            db.session.add(station)
        p = Product.query.first()
        if not p:
            p = Product(codice="P-BASE", descrizione="Prodotto Base", prezzo_vendita=10.0, aliquota_iva=22)
            db.session.add(p)
        db.session.commit()
        st_id = station.id
        p_id = p.id

    payload = {
        "pos_station_id": st_id,
        "metodo_pagamento": "contanti",
        "importo_pagato": 5.00, # Less than 10.00 total!
        "items": [
            {
                "product_id": p_id,
                "quantita": 1.0,
                "prezzo_unitario": 10.00
            }
        ]
    }

    res = client.post('/api/pos/sales', json=payload, headers=admin_headers)
    assert res.status_code == 400
    assert "insufficiente" in res.get_json()["error"].lower()
