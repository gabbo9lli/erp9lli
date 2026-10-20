from app import app
from models import db, Account

CHART_OF_ACCOUNTS = [
    # ATTIVO (1xxx)
    {"codice": "1001", "nome": "Cassa Contanti", "tipo": "attivo"},
    {"codice": "1002", "nome": "Banca c/c Principale", "tipo": "attivo"},
    {"codice": "1101", "nome": "Crediti v/Clienti", "tipo": "attivo"},
    {"codice": "2202", "nome": "Erario c/IVA a Credito", "tipo": "attivo"},

    # PASSIVO (2xxx / 3xxx)
    {"codice": "2001", "nome": "Debiti v/Fornitori", "tipo": "passivo"},
    {"codice": "2201", "nome": "Erario c/IVA a Debito", "tipo": "passivo"},
    {"codice": "3001", "nome": "Capitale Sociale e Riserve", "tipo": "passivo"},

    # COSTI (5xxx)
    {"codice": "5101", "nome": "Costi Merci c/Acquisti", "tipo": "costi"},
    {"codice": "5201", "nome": "Spese di Trasporto e Logistica", "tipo": "costi"},
    {"codice": "5301", "nome": "Spese e Commissioni Bancarie", "tipo": "costi"},

    # RICAVI (4xxx)
    {"codice": "4101", "nome": "Ricavi Vendite Prodotti Biologici", "tipo": "ricavi"},
    {"codice": "4201", "nome": "Ricavi Prestazioni e Cauzioni", "tipo": "ricavi"}
]

def seed_chart_of_accounts():
    added = 0
    for acc_data in CHART_OF_ACCOUNTS:
        existing = Account.query.filter_by(codice=acc_data["codice"]).first()
        if not existing:
            acc = Account(**acc_data)
            db.session.add(acc)
            added += 1
    if added > 0:
        db.session.commit()
    return added

if __name__ == '__main__':
    with app.app_context():
        print("Inizializzazione Piano dei Conti standard in corso...")
        count = seed_chart_of_accounts()
        print(f"Piano dei Conti completato: inseriti {count} nuovi conti.")
