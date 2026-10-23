import pytest
from datetime import date
from models import Account, JournalEntry, JournalItem

def test_account_and_journal_models(client, db_session):
    acc_cassa = Account(codice="1001", nome="Cassa Contanti", tipo="attivo")
    acc_banca = Account(codice="1002", nome="Banca c/c", tipo="attivo")
    db_session.add_all([acc_cassa, acc_banca])
    db_session.commit()

    entry = JournalEntry(
        numero=1,
        anno=2026,
        numero_completo="PN-2026-0001",
        data_registrazione=date.today(),
        data_competenza=date.today(),
        causale="Versamento contanti in banca",
        totale_dare=500.0,
        totale_avere=500.0,
        stato="confermata"
    )
    db_session.add(entry)
    db_session.commit()

    item1 = JournalItem(journal_entry_id=entry.id, account_id=acc_banca.id, dare=500.0, avere=0.0)
    item2 = JournalItem(journal_entry_id=entry.id, account_id=acc_cassa.id, dare=0.0, avere=500.0)
    db_session.add_all([item1, item2])
    db_session.commit()

    assert entry.id is not None
    assert len(entry.items) == 2
    assert entry.numero_completo == "PN-2026-0001"

def test_unbalanced_entry_rejected(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    from seed_accounting import seed_chart_of_accounts
    seed_chart_of_accounts(db_session)
    acc_banca = db_session.query(Account).filter_by(codice="1002").first()
    acc_ricavi = db_session.query(Account).filter_by(codice="4101").first()

    payload = {
        "causale": "Scrittura sbilanciata test",
        "items": [
            {"account_id": acc_banca.id, "dare": 100.0, "avere": 0.0},
            {"account_id": acc_ricavi.id, "dare": 0.0, "avere": 90.0}
        ]
    }
    res = client.post('/api/accounting/entries', json=payload, headers=admin_headers)
    assert res.status_code == 400
    assert "sbilanciata" in res.get_json()['error'].lower()

def test_balanced_entry_creation(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    from seed_accounting import seed_chart_of_accounts
    seed_chart_of_accounts(db_session)
    acc_banca = db_session.query(Account).filter_by(codice="1002").first()
    acc_ricavi = db_session.query(Account).filter_by(codice="4101").first()

    payload = {
        "causale": "Vendita bio incasso immediato",
        "items": [
            {"account_id": acc_banca.id, "dare": 150.0, "avere": 0.0},
            {"account_id": acc_ricavi.id, "dare": 0.0, "avere": 150.0}
        ]
    }
    res = client.post('/api/accounting/entries', json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.get_json()
    assert data['numero_completo'] == f"PN-{date.today().year}-0001"
    assert data['totale_dare'] == 150.0
    assert data['totale_avere'] == 150.0

def test_libro_giornale_report_json_and_csv(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    from seed_accounting import seed_chart_of_accounts
    seed_chart_of_accounts(db_session)
    acc_banca = db_session.query(Account).filter_by(codice="1002").first()
    acc_ricavi = db_session.query(Account).filter_by(codice="4101").first()

    client.post('/api/accounting/entries', json={
        "causale": "Test libro giornale",
        "items": [
            {"account_id": acc_banca.id, "dare": 150.0, "avere": 0.0},
            {"account_id": acc_ricavi.id, "dare": 0.0, "avere": 150.0}
        ]
    }, headers=admin_headers)

    # JSON report
    res_json = client.get('/api/accounting/reports/libro-giornale', headers=admin_headers)
    assert res_json.status_code == 200
    report_data = res_json.get_json()
    assert 'righe' in report_data
    assert report_data['totale_dare'] >= 150.0
    assert report_data['totale_avere'] == report_data['totale_dare']

    # CSV export
    res_csv = client.get('/api/accounting/reports/libro-giornale?format=csv', headers=admin_headers)
    assert res_csv.status_code == 200
    assert 'text/csv' in res_csv.headers['Content-Type']
    csv_text = res_csv.data.decode('utf-8')
    assert "Data;Numero;Causale;Codice;Conto;Partner;Dare;Avere" in csv_text

def test_mastro_running_balance(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    from seed_accounting import seed_chart_of_accounts
    seed_chart_of_accounts(db_session)
    acc_banca = db_session.query(Account).filter_by(codice="1002").first()
    acc_ricavi = db_session.query(Account).filter_by(codice="4101").first()
    b_id = acc_banca.id

    client.post('/api/accounting/entries', json={
        "causale": "Test mastro",
        "items": [
            {"account_id": acc_banca.id, "dare": 200.0, "avere": 0.0},
            {"account_id": acc_ricavi.id, "dare": 0.0, "avere": 200.0}
        ]
    }, headers=admin_headers)

    res = client.get(f'/api/accounting/reports/mastro?account_id={b_id}', headers=admin_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data['conto']['codice'] == "1002"
    assert len(data['movimenti']) > 0
    assert data['saldo_finale'] >= 200.0

    # CSV check for mastro
    res_csv = client.get(f'/api/accounting/reports/mastro?account_id={b_id}&format=csv', headers=admin_headers)
    assert res_csv.status_code == 200
    assert 'text/csv' in res_csv.headers['Content-Type']

def test_bilancio_di_verifica_balance(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    from seed_accounting import seed_chart_of_accounts
    seed_chart_of_accounts(db_session)
    acc_banca = db_session.query(Account).filter_by(codice="1002").first()
    acc_ricavi = db_session.query(Account).filter_by(codice="4101").first()

    client.post('/api/accounting/entries', json={
        "causale": "Test bilancio",
        "items": [
            {"account_id": acc_banca.id, "dare": 300.0, "avere": 0.0},
            {"account_id": acc_ricavi.id, "dare": 0.0, "avere": 300.0}
        ]
    }, headers=admin_headers)

    res = client.get('/api/accounting/reports/bilancio-verifica', headers=admin_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert 'conti' in data
    assert round(data['totale_dare'], 2) == round(data['totale_avere'], 2)

    # CSV check for bilancio
    res_csv = client.get('/api/accounting/reports/bilancio-verifica?format=csv', headers=admin_headers)
    assert res_csv.status_code == 200
    assert 'text/csv' in res_csv.headers['Content-Type']
