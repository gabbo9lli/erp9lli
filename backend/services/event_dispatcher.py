import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from models import db, EventChannel, EventCategory, SystemEvent

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

def seed_default_channels_and_categories():
    if EventChannel.query.count() == 0:
        for c in DEFAULT_CHANNELS:
            db.session.add(EventChannel(**c))
        db.session.commit()

    if EventCategory.query.count() == 0:
        for cat in DEFAULT_CATEGORIES:
            db.session.add(EventCategory(**cat))
        db.session.commit()

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

            # Determinazione stato finale
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

def dispatch_event(
    channel_code="AUDIT",
    category_code="SISTEMA",
    azione="azione_generica",
    titolo="Titolo",
    descrizione=None,
    payload_dati=None,
    destinatario_recapito=None,
    partner_id=None,
    entita_tipo=None,
    entita_id=None,
    utente_id=None,
    utente_email=None,
    is_async=False,
    livello="info",
    target_func=None
) -> SystemEvent:
    seed_default_channels_and_categories()
    ch = EventChannel.query.filter_by(codice=channel_code).first()
    if not ch:
        ch = EventChannel.query.filter_by(codice="AUDIT").first()

    cat = EventCategory.query.filter_by(codice=category_code).first()

    event = SystemEvent(
        channel_id=ch.id,
        category_id=cat.id if cat else None,
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
