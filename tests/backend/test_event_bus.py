import pytest
import time
from datetime import datetime
from models import EventChannel, EventCategory, SystemEvent

def test_event_models_persistence(client, db_session):
    ch = EventChannel(codice="AUDIT", nome="Audit Log", tipo_dispatcher="internal")
    cat = EventCategory(codice="LOGISTICA", nome="Logistica & Magazzino", colore_badge="teal")
    db_session.add_all([ch, cat])
    db_session.commit()

    event = SystemEvent(
        channel_id=ch.id,
        category_id=cat.id,
        azione="emissione_ddt",
        titolo="Emesso DDT-2026-0001",
        descrizione="Consegna merci completata",
        stato="completato",
        progresso=100
    )
    db_session.add(event)
    db_session.commit()

    assert event.id is not None
    assert event.channel.codice == "AUDIT"
    assert event.category.codice == "LOGISTICA"
    assert event.stato == "completato"

def test_dispatch_audit_event_synchronous(client, db_session):
    from services.event_dispatcher import dispatch_event

    event = dispatch_event(db_session, 
        channel_code="AUDIT",
        category_code="LOGISTICA",
        azione="emissione_ddt",
        titolo="Emesso DDT-2026-0001",
        descrizione="Bolla vendita per EcorNaturaSì",
        utente_email="gabbo@intrend.it",
        entita_tipo="delivery_note",
        entita_id=1
    )
    assert event.id is not None
    assert event.channel.codice == "AUDIT"
    assert event.category.codice == "LOGISTICA"
    assert event.stato == "completato"
    assert event.progresso == 100
    assert event.is_async is False

def test_dispatch_email_in_test_environment(client, db_session):
    from services.event_dispatcher import dispatch_event

    event = dispatch_event(db_session, 
        channel_code="EMAIL",
        category_code="PALLET",
        azione="sollecito_pallet",
        titolo="Sollecito Restituzione Buono Pallet BP-2026-0001",
        descrizione="Gentile Cliente, vi ricordiamo che i 15 pallet EPAL risultano a debito...",
        destinatario_recapito="cliente@bio.it",
        entita_tipo="pallet_receipt",
        entita_id=1
    )
    assert event.id is not None
    assert event.channel.codice == "EMAIL"
    assert event.stato == "test"
    assert "test" in event.note_esito.lower()
    assert event.destinatario_recapito == "cliente@bio.it"

def test_background_async_task_progress(client, db_session):
    from services.event_dispatcher import dispatch_event

    event = dispatch_event(db_session, 
        channel_code="EMAIL",
        category_code="PALLET",
        azione="invio_massivo_solleciti",
        titolo="Invio massivo solleciti pallet",
        payload_dati={"buoni_ids": [1, 2, 3]},
        is_async=True
    )
    assert event.id is not None
    assert event.is_async is True
    event_id = event.id

    # Wait briefly for background thread execution
    time.sleep(0.4)

    db_session.expire_all()
    refreshed = db_session.get(SystemEvent, event_id)
    assert refreshed.stato in ("completato", "test")
    assert refreshed.progresso == 100

def test_api_events_crud_and_channels(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    # 1. Channels list
    res_ch = client.get('/api/events/channels', headers=admin_headers)
    assert res_ch.status_code == 200
    channels = res_ch.json()
    assert any(c['codice'] == 'AUDIT' for c in channels)
    assert any(c['codice'] == 'EMAIL' for c in channels)

    # 2. Categories list
    res_cat = client.get('/api/events/categories', headers=admin_headers)
    assert res_cat.status_code == 200
    categories = res_cat.json()
    assert any(cat['codice'] == 'LOGISTICA' for cat in categories)

    # 3. Create synchronous event
    res_ev = client.post('/api/events', json={
        "channel_code": "AUDIT",
        "category_code": "VENDITE",
        "azione": "test_audit",
        "titolo": "Azione di Test",
        "descrizione": "Dettaglio dell'audit"
    }, headers=admin_headers)
    assert res_ev.status_code == 201
    ev_data = res_ev.json()
    assert ev_data['stato'] == "completato"
    assert ev_data['progresso'] == 100

def test_api_async_event_returns_202(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    # Launch asynchronous background event
    res = client.post('/api/events', json={
        "channel_code": "EMAIL",
        "category_code": "SISTEMA",
        "azione": "invio_batch_test",
        "titolo": "Elaborazione Notturna Batch",
        "is_async": True
    }, headers=admin_headers)
    assert res.status_code == 202
    data = res.json()
    assert data['is_async'] is True
    assert 'id' in data

def test_api_pallet_batch_solleciti_background(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    res = client.post('/api/pallets/batch-solleciti', headers=admin_headers)
    assert res.status_code == 202
    data = res.json()
    assert data['is_async'] is True
    assert data['azione'] == "sollecito_massivo_pallet"
