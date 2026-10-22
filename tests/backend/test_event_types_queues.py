import pytest
from datetime import datetime
from models import db, EventChannel, EventCategory, EventType, SystemEvent

def test_event_type_model_persistence(client):
    with client.application.app_context():
        ch = EventChannel(codice="EMAIL", nome="Email", tipo_dispatcher="smtp", richiede_destinatario=True)
        cat = EventCategory(codice="PALLET", nome="Pallet", colore_badge="deep-orange")
        db.session.add_all([ch, cat])
        db.session.commit()

        etype = EventType(
            codice="SOLLECITO_PALLET",
            nome="Sollecito Restituzione Pallet",
            channel_id=ch.id,
            category_id=cat.id,
            modalita_esecuzione="asincrono",
            coda_nome="emails"
        )
        db.session.add(etype)
        db.session.commit()

        assert etype.id is not None
        assert etype.modalita_esecuzione == "asincrono"
        assert etype.coda_nome == "emails"

def test_system_event_extended_fields(client):
    with client.application.app_context():
        ch = EventChannel(codice="AUDIT", nome="Audit", tipo_dispatcher="internal")
        db.session.add(ch)
        db.session.commit()

        etype = EventType(
            codice="EMISSIONE_DDT",
            nome="Emissione DDT",
            channel_id=ch.id,
            modalita_esecuzione="sincrono",
            coda_nome="default"
        )
        db.session.add(etype)
        db.session.commit()

        ev = SystemEvent(
            channel_id=ch.id,
            event_type_id=etype.id,
            coda_nome="default",
            rq_job_id="job-12345",
            azione="emissione_ddt",
            titolo="DDT-2026-0001",
            stato="completato"
        )
        db.session.add(ev)
        db.session.commit()

        assert ev.id is not None
        assert ev.event_type_id == etype.id
        assert ev.coda_nome == "default"
        assert ev.rq_job_id == "job-12345"
        assert ev.event_type.codice == "EMISSIONE_DDT"

def test_dispatch_event_declarative_async_from_event_type(client):
    from services.event_dispatcher import dispatch_event

    with client.application.app_context():
        event = dispatch_event(
            event_type_code="SOLLECITO_PALLET",
            titolo="Sollecito Bancali Test",
            destinatario_recapito="cliente@bio.it"
        )
        assert event.id is not None
        assert event.is_async is True
        assert event.coda_nome == "emails"
        assert event.channel.codice == "EMAIL"
        assert event.category.codice == "PALLET"

def test_dispatch_event_declarative_sync_from_event_type(client):
    from services.event_dispatcher import dispatch_event

    with client.application.app_context():
        event = dispatch_event(
            event_type_code="EMISSIONE_DDT",
            titolo="Bolla Vendita Test",
            descrizione="DDT registrato con successo"
        )
        assert event.id is not None
        assert event.is_async is False
        assert event.stato == "completato"
        assert event.progresso == 100
        assert event.channel.codice == "AUDIT"
        assert event.category.codice == "LOGISTICA"

def test_api_event_types_crud_and_policy_update(client):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    # 1. Get Event Types list
    res_list = client.get('/api/events/types', headers=admin_headers)
    assert res_list.status_code == 200
    types = res_list.get_json()
    assert isinstance(types, list)
    ddt_type = next((t for t in types if t['codice'] == 'EMISSIONE_DDT'), None)
    assert ddt_type is not None
    assert ddt_type['modalita_esecuzione'] == 'sincrono'
    ddt_id = ddt_type['id']

    # 2. Update policy dynamically via PUT (change to asincrono on coda 'default')
    put_res = client.put(f'/api/events/types/{ddt_id}', json={
        "modalita_esecuzione": "asincrono",
        "coda_nome": "default"
    }, headers=admin_headers)
    assert put_res.status_code == 200
    updated_data = put_res.get_json()
    assert updated_data['modalita_esecuzione'] == "asincrono"
    assert updated_data['coda_nome'] == "default"

def test_api_redis_queues_stats(client):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    res = client.get('/api/events/queues', headers=admin_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert 'queues' in data
    queue_names = [q['name'] for q in data['queues']]
    assert 'critical' in queue_names
    assert 'emails' in queue_names
    assert 'batch' in queue_names
    assert 'default' in queue_names

def test_api_event_types_policy_validation_rejected(client):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    res_list = client.get('/api/events/types', headers=admin_headers)
    types = res_list.get_json()
    first_id = types[0]['id']

    # Invalid modalita
    bad_res1 = client.put(f'/api/events/types/{first_id}', json={"modalita_esecuzione": "invalid_mode"}, headers=admin_headers)
    assert bad_res1.status_code == 400

    # Invalid queue
    bad_res2 = client.put(f'/api/events/types/{first_id}', json={"coda_nome": "unknown_queue"}, headers=admin_headers)
    assert bad_res2.status_code == 400
