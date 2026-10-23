import pytest
from datetime import date, datetime
from models import Account, AccountingCausal, EventType, JournalEntry

def test_accounting_causal_model_persistence(client, db_session):
    acc_crediti = Account(codice="1101", nome="Crediti Clienti", tipo="attivo")
    acc_ricavi = Account(codice="4101", nome="Ricavi Vendite Bio", tipo="ricavi")
    acc_iva = Account(codice="2201", nome="Erario c/IVA a Debito", tipo="passivo")
    db_session.add_all([acc_crediti, acc_ricavi, acc_iva])
    db_session.commit()

    causal = AccountingCausal(
        codice="VEND_FATT",
        descrizione="Fattura di Vendita a Cliente",
        tipo_registro="vendite",
        conto_dare_id=acc_crediti.id,
        conto_avere_id=acc_ricavi.id,
        conto_iva_id=acc_iva.id
    )
    db_session.add(causal)
    db_session.commit()

    assert causal.id is not None
    assert causal.conto_dare.codice == "1101"
    assert causal.conto_avere.codice == "4101"
    assert causal.conto_iva.codice == "2201"
    assert causal.to_dict()["codice"] == "VEND_FATT"

def test_seed_accounting_causals_and_event_type_link(client, db_session):
    from seed_accounting import seed_chart_of_accounts, seed_default_accounting_causals
    from services.event_dispatcher import seed_default_channels_and_categories
    from models import AccountingCausal, EventType

    seed_chart_of_accounts(db_session)
    seed_default_channels_and_categories(db_session)
    seed_default_accounting_causals(db_session)

    causals = db_session.query(AccountingCausal).all()
    codici = [c.codice for c in causals]
    assert "VEND_FATT" in codici
    assert "VEND_NC" in codici
    assert "INCASSO_RATA" in codici
    assert "CORRISPETTIVO" in codici
    assert "ACQ_MERCI" in codici
    assert "PAGAM_FORN" in codici

    # Check EventType links
    ev_fatt = db_session.query(EventType).filter_by(codice="EMISSIONE_FATTURA").first()
    assert ev_fatt is not None
    assert ev_fatt.accounting_causal is not None
    assert ev_fatt.accounting_causal.codice == "VEND_FATT"

    ev_inc = db_session.query(EventType).filter_by(codice="INCASSO_RATA").first()
    assert ev_inc is not None
    assert ev_inc.accounting_causal is not None
    assert ev_inc.accounting_causal.codice == "INCASSO_RATA"

def test_auto_accounting_and_event_on_invoice_creation(client, db_session):
    from seed_accounting import seed_chart_of_accounts, seed_default_accounting_causals
    from services.event_dispatcher import seed_default_channels_and_categories
    from models import Partner, Product, JournalEntry, SystemEvent, Invoice

    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    seed_chart_of_accounts(db_session)
    seed_default_channels_and_categories(db_session)
    seed_default_accounting_causals(db_session)

    cli = Partner(ragione_sociale="Cliente Bio Test", tipo="cliente", partita_iva="11223344556")
    p = Product(codice="P-VENDITA", descrizione="Mandarini Bio", prezzo_vendita=10.0, aliquota_iva=4)
    db_session.add_all([cli, p])
    db_session.commit()
    cli_id = cli.id
    p_id = p.id

    payload = {
        "cliente_id": cli_id,
        "tipo_documento": "TD01",
        "data_documento": "2026-10-22",
        "items": [
            {
                "product_id": p_id,
                "quantita": 10.0,
                "prezzo_unitario": 10.00,
                "aliquota_iva": 4.0
            }
        ]
    }

    res = client.post('/api/invoices', json=payload, headers=admin_headers)
    assert res.status_code == 201
    inv_data = res.get_json()
    inv_id = inv_data["id"]

    inv = db_session.get(Invoice, inv_id)
    # Check automatic JournalEntry
    je = db_session.query(JournalEntry).filter(JournalEntry.causale.like(f"%{inv.numero_completo}%")).first()
    assert je is not None
    assert je.causale_obj is not None
    assert je.causale_obj.codice == "VEND_FATT"
    assert abs(float(je.totale_dare) - float(je.totale_avere)) <= 0.001
    assert float(je.totale_dare) == float(inv.totale_fattura)

    # Check Event Bus
    ev = db_session.query(SystemEvent).filter_by(entita_tipo="invoice", entita_id=inv.id).first()
    assert ev is not None
    assert ev.event_type.codice == "EMISSIONE_FATTURA"

def test_auto_accounting_and_event_on_installment_pay(client, db_session):
    from seed_accounting import seed_chart_of_accounts, seed_default_accounting_causals
    from services.event_dispatcher import seed_default_channels_and_categories
    from models import Partner, Product, JournalEntry, SystemEvent, Invoice, InvoiceInstallment

    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    seed_chart_of_accounts(db_session)
    seed_default_channels_and_categories(db_session)
    seed_default_accounting_causals(db_session)

    cli = Partner(ragione_sociale="Cliente Rata Test", tipo="cliente")
    p = Product(codice="P-RATA", descrizione="Pere Bio", prezzo_vendita=5.0, aliquota_iva=4)
    db_session.add_all([cli, p])
    db_session.commit()
    cli_id = cli.id
    p_id = p.id

    inv_res = client.post('/api/invoices', json={
        "cliente_id": cli_id,
        "tipo_documento": "TD01",
        "items": [{"product_id": p_id, "quantita": 2.0, "prezzo_unitario": 5.0, "aliquota_iva": 4.0}]
    }, headers=admin_headers)
    assert inv_res.status_code == 201
    inv_id = inv_res.get_json()["id"]

    inv = db_session.get(Invoice, inv_id)
    assert len(inv.installments) > 0
    inst_id = inv.installments[0].id

    pay_res = client.post(f'/api/installments/{inst_id}/pay', headers=admin_headers)
    assert pay_res.status_code == 200

    # Check automatic JournalEntry for payment
    je = db_session.query(JournalEntry).filter(JournalEntry.causale.like(f"%{inv.numero_completo}%"), JournalEntry.id != inv.journal_entry_id if hasattr(inv, 'journal_entry_id') else True).order_by(JournalEntry.id.desc()).first()
    assert je is not None
    assert je.causale_obj is not None
    assert je.causale_obj.codice == "INCASSO_RATA"
    assert abs(float(je.totale_dare) - float(je.totale_avere)) <= 0.001

    # Check Event Bus for payment
    ev = db_session.query(SystemEvent).filter_by(entita_tipo="installment", entita_id=inst_id).first()
    assert ev is not None
    assert ev.event_type.codice == "INCASSO_RATA"

def test_auto_accounting_and_event_on_credit_note(client, db_session):
    from seed_accounting import seed_chart_of_accounts, seed_default_accounting_causals
    from services.event_dispatcher import seed_default_channels_and_categories
    from models import Partner, Product, JournalEntry, SystemEvent, Invoice

    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    seed_chart_of_accounts(db_session)
    seed_default_channels_and_categories(db_session)
    seed_default_accounting_causals(db_session)

    cli = Partner(ragione_sociale="Cliente Storno Test", tipo="cliente")
    p = Product(codice="P-STORNO", descrizione="Mele Bio Storno", prezzo_vendita=10.0, aliquota_iva=4)
    db_session.add_all([cli, p])
    db_session.commit()
    cli_id = cli.id
    p_id = p.id

    inv_res = client.post('/api/invoices', json={
        "cliente_id": cli_id,
        "tipo_documento": "TD01",
        "items": [{"product_id": p_id, "quantita": 5.0, "prezzo_unitario": 10.0, "aliquota_iva": 4.0}]
    }, headers=admin_headers)
    assert inv_res.status_code == 201
    inv_id = inv_res.get_json()["id"]

    inv = db_session.get(Invoice, inv_id)
    nc_items_payload = [{"invoice_item_id": it.id, "quantita_stornata": it.quantita} for it in inv.items]

    nc_res = client.post(f'/api/invoices/{inv_id}/credit-note', json={
        "causale_storno": "Reso per merce non conforme",
        "items": nc_items_payload
    }, headers=admin_headers)
    assert nc_res.status_code == 201
    nc_data = nc_res.get_json()
    nc_id = nc_data["id"]

    nc = db_session.get(Invoice, nc_id)
    # Check automatic JournalEntry for Credit Note
    je = db_session.query(JournalEntry).filter(JournalEntry.causale.like(f"%{nc.numero_completo}%")).first()
    assert je is not None
    assert je.causale_obj is not None
    assert je.causale_obj.codice == "VEND_NC"
    assert abs(float(je.totale_dare) - float(je.totale_avere)) <= 0.001

    # Check Event Bus
    ev = db_session.query(SystemEvent).filter_by(entita_tipo="invoice", entita_id=nc.id).first()
    assert ev is not None
    assert ev.event_type.codice == "EMISSIONE_FATTURA"

def test_api_accounting_causals_crud(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    # 1. GET
    res_list = client.get('/api/accounting/causals', headers=admin_headers)
    assert res_list.status_code == 200
    causals = res_list.get_json()
    assert isinstance(causals, list)
    first_causal = causals[0]

    # 2. PUT update
    res_put = client.put(f"/api/accounting/causals/{first_causal['id']}", json={
        "descrizione": "Nuova Descrizione Modificata"
    }, headers=admin_headers)
    assert res_put.status_code == 200
    assert res_put.get_json()["descrizione"] == "Nuova Descrizione Modificata"

    # 3. POST new
    res_post = client.post('/api/accounting/causals', json={
        "codice": "TEST_EXTRA",
        "descrizione": "Causale Extra di Test",
        "tipo_registro": "generale"
    }, headers=admin_headers)
    assert res_post.status_code == 201
    assert res_post.get_json()["codice"] == "TEST_EXTRA"
