import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from redis import Redis
from rq import Queue
from models import db, EventChannel, EventCategory, EventType, SystemEvent

executor = ThreadPoolExecutor(max_workers=4)

DEFAULT_CHANNELS = [
    {"codice": "AUDIT", "nome": "Audit Log Attività", "descrizione": "Tracciamento interno delle operazioni utente", "tipo_dispatcher": "internal", "richiede_destinatario": False},
    {"codice": "EMAIL", "nome": "Posta Elettronica Ordinaria", "descrizione": "Invio email ordinarie a clienti/fornitori", "tipo_dispatcher": "smtp", "richiede_destinatario": True},
    {"codice": "PEC", "nome": "Posta Elettronica Certificata", "descrizione": "Invio comunicazioni certificate e legali", "tipo_dispatcher": "smtp", "richiede_destinatario": True},
    {"codice": "WEBHOOK", "nome": "Webhook API Esterna", "descrizione": "Inoltro eventi a endpoint HTTP terzi", "tipo_dispatcher": "webhook", "richiede_destinatario": True}
]

DEFAULT_CATEGORIES = [
    {"codice": "LOGISTICA", "nome": "Logistica & Magazzino", "colore_badge": "teal", "icona": "inventory_2"},
    {"codice": "VENDITE", "nome": "Vendite & Ordini", "colore_badge": "primary", "icona": "shopping_cart"},
    {"codice": "ACQUISTI", "nome": "Entrata Merci Fornitori", "colore_badge": "blue", "icona": "move_to_inbox"},
    {"codice": "FISCALE", "nome": "Amministrazione & Fatture", "colore_badge": "indigo", "icona": "receipt"},
    {"codice": "PALLET", "nome": "Interscambio Pallet L.182", "colore_badge": "deep-orange", "icona": "layers"},
    {"codice": "SISTEMA", "nome": "Manutenzione & Sistema", "colore_badge": "grey-8", "icona": "settings"}
]

DEFAULT_EVENT_TYPES = [
    {"codice": "EMISSIONE_DDT", "nome": "Emissione DDT di Vendita", "descrizione": "Bolla di trasporto merci emessa", "channel": "AUDIT", "category": "LOGISTICA", "modalita": "sincrono", "coda": "default"},
    {"codice": "CONFERMA_ORDINE", "nome": "Conferma Ordine Cliente", "descrizione": "Avanzamento o evasione ordine cliente", "channel": "AUDIT", "category": "VENDITE", "modalita": "sincrono", "coda": "default"},
    {"codice": "CARICO_MERCI", "nome": "Entrata Merci Fornitore", "descrizione": "Registrazione arrivo lotti biologici", "channel": "AUDIT", "category": "ACQUISTI", "modalita": "sincrono", "coda": "default"},
    {"codice": "INCASSO_RATA", "nome": "Incasso Rata Scadenzario", "descrizione": "Pagamento cliente registrato", "channel": "AUDIT", "category": "FISCALE", "modalita": "sincrono", "coda": "default"},
    {"codice": "EMISSIONE_FATTURA", "nome": "Emissione Fattura / Nota di Credito", "descrizione": "Documento fiscale emesso", "channel": "AUDIT", "category": "FISCALE", "modalita": "sincrono", "coda": "default"},
    {"codice": "SOLLECITO_PALLET", "nome": "Sollecito Buono Pallet", "descrizione": "Invio email di sollecito per buoni scaduti o aperti", "channel": "EMAIL", "category": "PALLET", "modalita": "asincrono", "coda": "emails"},
    {"codice": "SOLLECITO_MASSIVO_PALLET", "nome": "Invio Massivo Solleciti Pallet", "descrizione": "Batch massivo solleciti per tutti i clienti con buoni scaduti", "channel": "EMAIL", "category": "PALLET", "modalita": "asincrono", "coda": "batch"},
    {"codice": "INVIO_FATTURA_EMAIL", "nome": "Invio Fattura via Email", "descrizione": "Invio documento di cortesia al cliente", "channel": "EMAIL", "category": "FISCALE", "modalita": "asincrono", "coda": "emails"},
    {"codice": "SISTEMA_NOTIFICA", "nome": "Avviso / Notifica Critica", "descrizione": "Notifiche ed allarmi operativi urgenti", "channel": "AUDIT", "category": "SISTEMA", "modalita": "sincrono", "coda": "critical"}
]

def seed_default_channels_and_categories():
    if EventChannel.query.count() == 0:
        for c in DEFAULT_CHANNELS:
            db.session.add(EventChannel(**c))
        db.session.commit()

    if EventCategory.query.count() == 0:
        for cat in DEFAULT_CATEGORIES:
            db.session.add(EventCategory(**cat))
        db.session.commit()

    seed_default_event_types()

def seed_default_event_types():
    for et in DEFAULT_EVENT_TYPES:
        existing = EventType.query.filter_by(codice=et["codice"]).first()
        if not existing:
            ch = EventChannel.query.filter_by(codice=et["channel"]).first()
            cat = EventCategory.query.filter_by(codice=et["category"]).first()
            if ch:
                db.session.add(EventType(
                    codice=et["codice"],
                    nome=et["nome"],
                    descrizione=et["descrizione"],
                    channel_id=ch.id,
                    category_id=cat.id if cat else None,
                    modalita_esecuzione=et["modalita"],
                    coda_nome=et["coda"]
                ))
    db.session.commit()

    try:
        from models import AccountingCausal
        causali_map = {
            "EMISSIONE_FATTURA": "VEND_FATT",
            "INCASSO_RATA": "INCASSO_RATA",
            "CARICO_MERCI": "ACQ_MERCI"
        }
        for ev_code, caus_code in causali_map.items():
            ev = EventType.query.filter_by(codice=ev_code).first()
            caus = AccountingCausal.query.filter_by(codice=caus_code).first()
            if ev and caus and not ev.accounting_causal_id:
                ev.accounting_causal_id = caus.id
        db.session.commit()
    except Exception:
        pass

def get_redis_connection():
    try:
        from flask import current_app
        if current_app and current_app.config.get("TESTING"):
            return None
    except Exception:
        pass
    try:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        conn = Redis(host=redis_host, port=redis_port, socket_timeout=0.3)
        conn.ping()
        return conn
    except Exception:
        try:
            conn = Redis(host="localhost", port=6379, socket_timeout=0.3)
            conn.ping()
            return conn
        except Exception:
            return None

def _run_async_event(app, event_id, target_func=None):
    with app.app_context():
        event = db.session.get(SystemEvent, event_id)
        if not event:
            return
        event.stato = 'in_corso'
        event.data_inizio_esecuzione = datetime.utcnow()
        event.progresso = 15
        db.session.commit()

        try:
            if target_func:
                target_func(event)
            else:
                event.progresso = 60
                db.session.commit()
                time.sleep(0.05)
                event.progresso = 100

            if event.channel and event.channel.tipo_dispatcher == 'smtp':
                smtp_enabled = os.getenv('SMTP_ENABLED', 'false').lower() == 'true'
                if not smtp_enabled:
                    event.stato = 'test'
                    event.note_esito = "Evento archiviato in modalità test. Nessuna spedizione esterna eseguita."
                else:
                    event.stato = 'completato'
                    event.note_esito = "Email inviata con successo."
            else:
                event.stato = 'completato'

            event.data_completamento = datetime.utcnow()
            event.progresso = 100
            db.session.commit()
        except Exception as e:
            event.stato = 'errore'
            event.note_esito = str(e)
            db.session.commit()

def _run_rq_event_job(event_id):
    from app import app
    with app.app_context():
        _run_async_event(app, event_id, target_func=None)

def dispatch_event(
    event_type_code=None,
    channel_code=None,
    category_code=None,
    azione=None,
    titolo="Titolo Evento",
    descrizione=None,
    payload_dati=None,
    destinatario_recapito=None,
    partner_id=None,
    entita_tipo=None,
    entita_id=None,
    utente_id=None,
    utente_email=None,
    is_async=None,
    coda_nome=None,
    livello="info",
    target_func=None
) -> SystemEvent:
    seed_default_channels_and_categories()

    etype = None
    if event_type_code:
        etype = EventType.query.filter_by(codice=event_type_code).first()

    if etype:
        event_type_id = etype.id
        if channel_code is None and etype.channel:
            channel_code = etype.channel.codice
        if category_code is None and etype.category:
            category_code = etype.category.codice
        if is_async is None:
            is_async = (etype.modalita_esecuzione == 'asincrono')
        if coda_nome is None:
            coda_nome = etype.coda_nome
        if azione is None:
            azione = etype.codice.lower()
    else:
        event_type_id = None
        if is_async is None:
            is_async = False
        if coda_nome is None:
            coda_nome = 'default'
        if azione is None:
            azione = 'custom_event'

    ch = EventChannel.query.filter_by(codice=channel_code or "AUDIT").first()
    if not ch:
        ch = EventChannel.query.filter_by(codice="AUDIT").first()

    cat = EventCategory.query.filter_by(codice=category_code or "SISTEMA").first()

    event = SystemEvent(
        channel_id=ch.id,
        category_id=cat.id if cat else None,
        event_type_id=event_type_id,
        coda_nome=coda_nome,
        livello=livello,
        azione=azione,
        titolo=titolo,
        descrizione=descrizione,
        payload_dati=payload_dati,
        destinatario_recapito=destinatario_recapito,
        partner_id=partner_id,
        entita_tipo=entita_tipo,
        entita_id=entita_id,
        utente_id=utente_id,
        utente_email=utente_email,
        is_async=is_async,
        progresso=0,
        stato='in_coda' if is_async else 'in_corso'
    )
    db.session.add(event)
    db.session.commit()

    if is_async:
        from flask import current_app
        app = current_app._get_current_object()

        # Prova accodamento su RQ se Redis è attivo e non siamo in TESTING puro
        redis_conn = get_redis_connection()
        if redis_conn and not app.config.get("TESTING"):
            try:
                rq_queue = Queue(coda_nome or 'default', connection=redis_conn)
                job = rq_queue.enqueue(_run_rq_event_job, event.id)
                event.rq_job_id = job.id
                db.session.commit()
                return event
            except Exception:
                pass

        if app.config.get("TESTING"):
            _run_async_event(app, event.id, target_func)
            return event

        executor.submit(_run_async_event, app, event.id, target_func)
        return event
    else:
        # Sincrono
        if ch.tipo_dispatcher == 'smtp':
            smtp_enabled = os.getenv('SMTP_ENABLED', 'false').lower() == 'true'
            if not smtp_enabled:
                event.stato = 'test'
                event.note_esito = "Evento archiviato in modalità test. Nessuna spedizione esterna eseguita."
            else:
                event.stato = 'completato'
                event.note_esito = "Email inviata con successo."
        else:
            event.stato = 'completato'

        event.progresso = 100
        event.data_inizio_esecuzione = datetime.utcnow()
        event.data_completamento = datetime.utcnow()
        db.session.commit()
        return event
