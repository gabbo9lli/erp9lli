from sqlalchemy.orm import Session
from database import SessionLocal
from models import Account, AccountingCausal, EventType

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

DEFAULT_ACCOUNTING_CAUSALS = [
    {
        "codice": "VEND_FATT",
        "descrizione": "Fattura di Vendita a Cliente",
        "tipo_registro": "vendite",
        "conto_dare": "1101",
        "conto_avere": "4101",
        "conto_iva": "2201",
        "template_descrizione": "Fattura n. {numero} del {data} a {cliente}"
    },
    {
        "codice": "VEND_NC",
        "descrizione": "Nota di Credito a Cliente",
        "tipo_registro": "vendite",
        "conto_dare": "4101",
        "conto_avere": "1101",
        "conto_iva": "2201",
        "template_descrizione": "Nota di Credito n. {numero} su FT {origine}"
    },
    {
        "codice": "INCASSO_RATA",
        "descrizione": "Incasso Rata Fattura Cliente",
        "tipo_registro": "generale",
        "conto_dare": "1002",
        "conto_avere": "1101",
        "conto_iva": None,
        "template_descrizione": "Incasso rata {rata}/{tot_rate} fattura {numero}"
    },
    {
        "codice": "CORRISPETTIVO",
        "descrizione": "Corrispettivi Vendita Banco POS",
        "tipo_registro": "corrispettivi",
        "conto_dare": "1001",
        "conto_avere": "4101",
        "conto_iva": "2201",
        "template_descrizione": "Corrispettivo scontrino {scontrino}"
    },
    {
        "codice": "ACQ_MERCI",
        "descrizione": "Acquisto Merci da Fornitore",
        "tipo_registro": "acquisti",
        "conto_dare": "5101",
        "conto_avere": "2001",
        "conto_iva": "2202",
        "template_descrizione": "Fattura acquisto n. {numero} da {fornitore}"
    },
    {
        "codice": "PAGAM_FORN",
        "descrizione": "Pagamento Fattura Fornitore",
        "tipo_registro": "generale",
        "conto_dare": "2001",
        "conto_avere": "1002",
        "conto_iva": None,
        "template_descrizione": "Pagamento fornitore {fornitore}"
    }
]

def seed_chart_of_accounts(db: Session) -> int:
    if db.query(Account).count() >= len(CHART_OF_ACCOUNTS):
        return 0
    added = 0
    for acc_data in CHART_OF_ACCOUNTS:
        existing = db.query(Account).filter_by(codice=acc_data["codice"]).first()
        if not existing:
            acc = Account(**acc_data)
            db.add(acc)
            added += 1
    if added > 0:
        db.commit()
    return added

def seed_default_accounting_causals(db: Session) -> int:
    seed_chart_of_accounts(db)
    if db.query(AccountingCausal).count() >= len(DEFAULT_ACCOUNTING_CAUSALS):
        return 0

    added = 0
    for c_data in DEFAULT_ACCOUNTING_CAUSALS:
        existing = db.query(AccountingCausal).filter_by(codice=c_data["codice"]).first()
        acc_dare = db.query(Account).filter_by(codice=c_data["conto_dare"]).first() if c_data.get("conto_dare") else None
        acc_avere = db.query(Account).filter_by(codice=c_data["conto_avere"]).first() if c_data.get("conto_avere") else None
        acc_iva = db.query(Account).filter_by(codice=c_data["conto_iva"]).first() if c_data.get("conto_iva") else None

        if not existing:
            causal = AccountingCausal(
                codice=c_data["codice"],
                descrizione=c_data["descrizione"],
                tipo_registro=c_data["tipo_registro"],
                conto_dare_id=acc_dare.id if acc_dare else None,
                conto_avere_id=acc_avere.id if acc_avere else None,
                conto_iva_id=acc_iva.id if acc_iva else None,
                template_descrizione=c_data.get("template_descrizione")
            )
            db.add(causal)
            added += 1

    if added > 0:
        db.commit()

    causali_map = {
        "EMISSIONE_FATTURA": "VEND_FATT",
        "INCASSO_RATA": "INCASSO_RATA",
        "CARICO_MERCI": "ACQ_MERCI"
    }
    for ev_code, caus_code in causali_map.items():
        ev = db.query(EventType).filter_by(codice=ev_code).first()
        caus = db.query(AccountingCausal).filter_by(codice=caus_code).first()
        if ev and caus and not ev.accounting_causal_id:
            ev.accounting_causal_id = caus.id
    db.commit()
    return added

if __name__ == '__main__':
    with SessionLocal() as db:
        print("Inizializzazione Piano dei Conti standard in corso...")
        count = seed_chart_of_accounts(db)
        print(f"Piano dei Conti completato: inseriti {count} nuovi conti.")
        c_count = seed_default_accounting_causals(db)
        print(f"Causali Contabili completate: inserite {c_count} nuove causali.")
