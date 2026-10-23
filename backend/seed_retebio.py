import sys
import os

from sqlalchemy.orm import Session
from database import SessionLocal
from models import Partner, Product

PARTNERS_DATA = [
    # --- CLIENTI (Canale Specializzato Bio e GDO) ---
    {
        "ragione_sociale": "EcorNaturaSì SpA",
        "tipo": "cliente",
        "partita_iva": "IT02010550263",
        "codice_fiscale": "02010550263",
        "indirizzo": "Via De Gasperi 5/A",
        "cap": "31044",
        "citta": "Montebelluna",
        "provincia": "TV",
        "nazione": "IT",
        "codice_sdi": "SUBM70N",
        "pec": "ecornaturasi@legalmail.it",
        "istituto_certificatore": "CCPB",
        "iban": "IT60X0542811101000000123456",
        "condizioni_pagamento": "60gg fm"
    },
    {
        "ragione_sociale": "Coop Alleanza 3.0 Soc. Coop.",
        "tipo": "cliente",
        "partita_iva": "IT03503411203",
        "codice_fiscale": "03503411203",
        "indirizzo": "Via Villanova 29/7",
        "cap": "40055",
        "citta": "Castenaso",
        "provincia": "BO",
        "nazione": "IT",
        "codice_sdi": "M5UXCR1",
        "pec": "coopalleanza3.0@pec.coop.it",
        "istituto_certificatore": "ICEA",
        "iban": "IT75Y0200802435000000654321",
        "condizioni_pagamento": "60gg fm"
    },
    {
        "ragione_sociale": "Bio c' Bon Italia Srl",
        "tipo": "cliente",
        "partita_iva": "IT08611840968",
        "codice_fiscale": "08611840968",
        "indirizzo": "Corso Magenta 64",
        "cap": "20123",
        "citta": "Milano",
        "provincia": "MI",
        "nazione": "IT",
        "codice_sdi": "KRRH6B9",
        "pec": "biocbonitalia@pec.it",
        "istituto_certificatore": "Ecocert",
        "iban": "IT12A0306909606100000098765",
        "condizioni_pagamento": "30gg fm"
    },
    {
        "ragione_sociale": "Conad Centro Nord Soc. Coop.",
        "tipo": "cliente",
        "partita_iva": "IT00140910355",
        "codice_fiscale": "00140910355",
        "indirizzo": "Via Fratelli Cervi 14",
        "cap": "42040",
        "citta": "Campegine",
        "provincia": "RE",
        "nazione": "IT",
        "codice_sdi": "0000000",
        "pec": "conadcentronord@pec.it",
        "istituto_certificatore": "Bioagricert",
        "iban": "IT99Z0303212345010000011223",
        "condizioni_pagamento": "60gg fm"
    },

    # --- FORNITORI AGRICOLI BIOLOGICI ---
    {
        "ragione_sociale": "Soc. Agr. BioFrutta Romagna SS",
        "tipo": "fornitore",
        "partita_iva": "IT04218760408",
        "codice_fiscale": "04218760408",
        "indirizzo": "Via Emilia Levante 142",
        "cap": "47521",
        "citta": "Cesena",
        "provincia": "FC",
        "nazione": "IT",
        "codice_sdi": "USAL8PV",
        "pec": "biofruttaromagna@pec.it",
        "istituto_certificatore": "CCPB",
        "iban": "IT44C0605513200000000012345",
        "condizioni_pagamento": "30gg fm"
    },
    {
        "ragione_sociale": "Az. Agr. Terre di Puglia Bio",
        "tipo": "fornitore",
        "partita_iva": "IT07321980721",
        "codice_fiscale": "07321980721",
        "indirizzo": "Contrada Torre Spagnola snc",
        "cap": "70014",
        "citta": "Conversano",
        "provincia": "BA",
        "nazione": "IT",
        "codice_sdi": "BA77BIO",
        "pec": "terredipugliabio@pec.it",
        "istituto_certificatore": "ICEA",
        "iban": "IT88D0503416001000000099887",
        "condizioni_pagamento": "30gg d.f."
    },
    {
        "ragione_sociale": "Cooperativa Agr. Valle del Chiese",
        "tipo": "fornitore",
        "partita_iva": "IT00128940228",
        "codice_fiscale": "00128940228",
        "indirizzo": "Via delle Mele 3",
        "cap": "38083",
        "citta": "Borgo Chiese",
        "provincia": "TN",
        "nazione": "IT",
        "codice_sdi": "TN00BIO",
        "pec": "valledelchiese@pec.it",
        "istituto_certificatore": "Bioagricert",
        "iban": "IT11E0807801234000000554433",
        "condizioni_pagamento": "60gg fm"
    },

    # --- VETTORI LOGISTICI ---
    {
        "ragione_sociale": "LD Trasporti Srl",
        "tipo": "vettore",
        "partita_iva": "IT01894520067",
        "codice_fiscale": "01894520067",
        "indirizzo": "Strada Statale per Casale 12",
        "cap": "15121",
        "citta": "Alessandria",
        "provincia": "AL",
        "nazione": "IT",
        "codice_sdi": "LDTRASP",
        "pec": "ldtrasporti@legalmail.it",
        "iban": "IT33F0200810400000100200300",
        "condizioni_pagamento": "30gg fm"
    },
    {
        "ragione_sociale": "Interfrigo Logistica Refrigerata SpA",
        "tipo": "vettore",
        "partita_iva": "IT02345670361",
        "codice_fiscale": "02345670361",
        "indirizzo": "Via dell'Autostrada 88",
        "cap": "41122",
        "citta": "Modena",
        "provincia": "MO",
        "nazione": "IT",
        "codice_sdi": "INTFRIG",
        "pec": "interfrigo@pec.it",
        "iban": "IT55G0303212900010000088776",
        "condizioni_pagamento": "30gg fm"
    }
]

PRODUCTS_DATA = [
    # --- ORTOFRUTTA FRESCA BIOLOGICA (IVA 4%, In Scadenza True) ---
    {
        "codice": "BIO-MELA-GLD",
        "descrizione": "Mele Golden Bio Val di Non (cal. 75/80)",
        "descrizione_en": "Organic Golden Delicious Apples",
        "categoria": "fresco",
        "unita_misura": "KG",
        "peso_netto": 1.0,
        "peso_lordo": 1.05,
        "tara": 0.05,
        "in_scadenza": True,
        "scorta_minima": 100.0,
        "prezzo_vendita": 2.40,
        "prezzo_acquisto": 1.30,
        "aliquota_iva": 4,
        "codice_nc": "08081080"
    },
    {
        "codice": "BIO-ARAN-TRC",
        "descrizione": "Arance Tarocco Bio Sicilia (cal. 4/6)",
        "descrizione_en": "Organic Blood Oranges Tarocco",
        "categoria": "fresco",
        "unita_misura": "KG",
        "peso_netto": 1.0,
        "peso_lordo": 1.06,
        "tara": 0.06,
        "in_scadenza": True,
        "scorta_minima": 150.0,
        "prezzo_vendita": 2.20,
        "prezzo_acquisto": 1.10,
        "aliquota_iva": 4,
        "codice_nc": "08051020"
    },
    {
        "codice": "BIO-KIWI-HYW",
        "descrizione": "Kiwi Hayward Bio Romagna (cal. 95/105g)",
        "descrizione_en": "Organic Kiwi Hayward",
        "categoria": "fresco",
        "unita_misura": "KG",
        "peso_netto": 1.0,
        "peso_lordo": 1.08,
        "tara": 0.08,
        "in_scadenza": True,
        "scorta_minima": 80.0,
        "prezzo_vendita": 3.80,
        "prezzo_acquisto": 2.10,
        "aliquota_iva": 4,
        "codice_nc": "08105000"
    },
    {
        "codice": "BIO-POM-DAT",
        "descrizione": "Pomodoro Datterino Bio in Vaschetta 500g",
        "descrizione_en": "Organic Datterino Tomatoes 500g",
        "categoria": "fresco",
        "unita_misura": "PZ",
        "peso_netto": 0.5,
        "peso_lordo": 0.54,
        "tara": 0.04,
        "in_scadenza": True,
        "scorta_minima": 50.0,
        "prezzo_vendita": 2.15,
        "prezzo_acquisto": 1.25,
        "aliquota_iva": 4,
        "codice_nc": "07020000"
    },
    {
        "codice": "BIO-CAROT-ROM",
        "descrizione": "Carote con Foglia Bio Romagna (mazzo)",
        "descrizione_en": "Organic Bunch Carrots",
        "categoria": "fresco",
        "unita_misura": "KG",
        "peso_netto": 1.0,
        "peso_lordo": 1.05,
        "tara": 0.05,
        "in_scadenza": True,
        "scorta_minima": 60.0,
        "prezzo_vendita": 1.85,
        "prezzo_acquisto": 0.90,
        "aliquota_iva": 4,
        "codice_nc": "07061000"
    },

    # --- TRASFORMATI BIOLOGICI (In Scadenza True) ---
    {
        "codice": "BIO-PASS-700",
        "descrizione": "Passata di Pomodoro Bio Tradizionale 700g",
        "descrizione_en": "Organic Tomato Puree 700g",
        "categoria": "trasformato",
        "unita_misura": "PZ",
        "peso_netto": 0.7,
        "peso_lordo": 1.05,
        "tara": 0.35,
        "in_scadenza": True,
        "scorta_minima": 200.0,
        "prezzo_vendita": 1.95,
        "prezzo_acquisto": 1.05,
        "aliquota_iva": 10,
        "codice_nc": "20029011"
    },
    {
        "codice": "BIO-OLIO-EVO1L",
        "descrizione": "Olio Extra Vergine di Oliva Bio 100% Italiano 1L",
        "descrizione_en": "Organic Extra Virgin Olive Oil 1L",
        "categoria": "trasformato",
        "unita_misura": "PZ",
        "peso_netto": 0.92,
        "peso_lordo": 1.45,
        "tara": 0.53,
        "in_scadenza": True,
        "scorta_minima": 120.0,
        "prezzo_vendita": 12.50,
        "prezzo_acquisto": 8.20,
        "aliquota_iva": 4,
        "codice_nc": "15091000"
    },
    {
        "codice": "BIO-COMP-MIRT",
        "descrizione": "Composta Artigianale di Mirtilli Bio 220g",
        "descrizione_en": "Organic Blueberry Jam 220g",
        "categoria": "trasformato",
        "unita_misura": "PZ",
        "peso_netto": 0.22,
        "peso_lordo": 0.38,
        "tara": 0.16,
        "in_scadenza": True,
        "scorta_minima": 40.0,
        "prezzo_vendita": 3.90,
        "prezzo_acquisto": 2.20,
        "aliquota_iva": 10,
        "codice_nc": "20079939"
    },

    # --- IMBALLAGGI E CAUZIONI (In Scadenza False, IVA 22%) ---
    {
        "codice": "IMB-PALLET-EPAL",
        "descrizione": "Pallet EPAL Interscambio 80x120 Usato Garantito (L. 182/2025)",
        "descrizione_en": "Standard EPAL Pallet 80x120",
        "categoria": "imballo",
        "unita_misura": "PZ",
        "peso_netto": 25.0,
        "peso_lordo": 25.0,
        "tara": 25.0,
        "in_scadenza": False,
        "scorta_minima": 500.0,
        "prezzo_vendita": 14.50,
        "prezzo_acquisto": 11.00,
        "aliquota_iva": 22,
        "codice_nc": "44152020"
    },
    {
        "codice": "IMB-CASSA-CPR",
        "descrizione": "Cassa Plastica Pieghevole CPR System 40x60",
        "descrizione_en": "CPR Reusable Folding Crate 40x60",
        "categoria": "imballo",
        "unita_misura": "PZ",
        "peso_netto": 1.8,
        "peso_lordo": 1.8,
        "tara": 1.8,
        "in_scadenza": False,
        "scorta_minima": 1000.0,
        "prezzo_vendita": 2.50,
        "prezzo_acquisto": 1.80,
        "aliquota_iva": 22,
        "codice_nc": "39231090"
    }
]

def seed_data(db: Session = None):
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        added_partners = 0
        added_products = 0

        # 1. Popola i Partner
        for p_data in PARTNERS_DATA:
            existing = db.query(Partner).filter_by(ragione_sociale=p_data["ragione_sociale"]).first()
            if not existing:
                partner = Partner(**p_data)
                db.add(partner)
                added_partners += 1

        # 2. Popola i Prodotti
        for prod_data in PRODUCTS_DATA:
            existing = db.query(Product).filter_by(codice=prod_data["codice"]).first()
            if not existing:
                product = Product(**prod_data)
                db.add(product)
                added_products += 1

        if added_partners > 0 or added_products > 0:
            db.commit()

        return added_partners, added_products
    finally:
        if close_session:
            db.close()

if __name__ == '__main__':
    with SessionLocal() as db:
        print("Avvio seed del dataset ReteBio in corso...")
        p_count, prod_count = seed_data(db)
        print(f"Seed completato con successo: inseriti {p_count} Partner e {prod_count} Prodotti.")
