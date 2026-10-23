import pytest
from datetime import date
from models import Partner, Product, DeliveryNote, DeliveryNoteItem, Invoice, InvoiceItem, InvoiceInstallment
import xml.etree.ElementTree as ET

def test_generate_sdi_xml_differita_td24(client, db_session):
    from services.sdi_service import generate_sdi_xml, validate_sdi_invoice

    customer = Partner(
        ragione_sociale="Supermercati Bio Italia SpA",
        partita_iva="01234567890",
        codice_fiscale="01234567890",
        codice_sdi="M5UXCR1",
        pec="bioitalia@pec.it",
        indirizzo="Via Roma 100",
        cap="20121",
        citta="Milano",
        provincia="MI",
        nazione="IT",
        tipo="cliente"
    )
    prod = Product(codice="ART-MELA-BIO", descrizione="Mele Bio Val di Non", prezzo_vendita=2.5)
    db_session.add_all([customer, prod])
    db_session.commit()

    ddt = DeliveryNote(
        numero=1,
        anno=2026,
        numero_completo="DDT-2026-0001",
        data_documento=date(2026, 10, 20),
        cliente_id=customer.id
    )
    db_session.add(ddt)
    db_session.commit()

    invoice = Invoice(
        numero=1,
        anno=2026,
        numero_completo="FT-2026-0001",
        tipo_documento="TD24",
        data_documento=date(2026, 10, 21),
        cliente_id=customer.id,
        condizioni_pagamento="30/60 gg fm",
        esigibilita_iva="I",
        totale_imponibile=250.0,
        totale_imposta=10.0,
        totale_fattura=260.0,
        castelletto_iva={"4": {"imponibile": 250.0, "imposta": 10.0}},
        stato="emessa"
    )
    db_session.add(invoice)
    db_session.commit()

    item = InvoiceItem(
        invoice_id=invoice.id,
        product_id=prod.id,
        delivery_note_id=ddt.id,
        descrizione="Mele Bio Val di Non",
        unita_misura="KG",
        quantita=100.0,
        prezzo_unitario=2.5,
        aliquota_iva=4,
        imponibile_riga=250.0
    )
    inst1 = InvoiceInstallment(
        invoice_id=invoice.id,
        numero_rata=1,
        totale_rate=2,
        data_scadenza=date(2026, 11, 30),
        importo=130.0,
        stato="aperta"
    )
    inst2 = InvoiceInstallment(
        invoice_id=invoice.id,
        numero_rata=2,
        totale_rate=2,
        data_scadenza=date(2026, 12, 31),
        importo=130.0,
        stato="aperta"
    )
    db_session.add_all([item, inst1, inst2])
    db_session.commit()

    # Test validation
    val_res = validate_sdi_invoice(invoice)
    assert val_res['valido'] is True
    assert len(val_res['errori']) == 0

    # Test XML generation
    xml_str, filename = generate_sdi_xml(invoice)
    assert filename.startswith("IT")
    assert filename.endswith(".xml")

    root = ET.fromstring(xml_str)
    # Check Header
    header = root.find("FatturaElettronicaHeader")
    assert header is not None
    assert header.find("DatiTrasmissione/FormatoTrasmissione").text == "FPR12"
    assert header.find("DatiTrasmissione/CodiceDestinatario").text == "M5UXCR1"
    assert header.find("CessionarioCommittente/DatiAnagrafici/Anagrafica/Denominazione").text == "Supermercati Bio Italia SpA"

    # Check Body
    body = root.find("FatturaElettronicaBody")
    assert body is not None
    assert body.find("DatiGenerali/DatiGeneraliDocumento/TipoDocumento").text == "TD24"
    assert body.find("DatiGenerali/DatiGeneraliDocumento/Numero").text == "FT-2026-0001"
    assert body.find("DatiGenerali/DatiGeneraliDocumento/ImportoTotaleDocumento").text == "260.00"

    # Check DatiDDT
    ddt_node = body.find("DatiGenerali/DatiDDT")
    assert ddt_node is not None
    assert ddt_node.find("NumeroDDT").text == "DDT-2026-0001"
    assert ddt_node.find("DataDDT").text == "2026-10-20"

    # Check DatiBeniServizi
    linea = body.find("DatiBeniServizi/DettaglioLinee")
    assert linea is not None
    assert linea.find("Descrizione").text == "Mele Bio Val di Non"
    assert linea.find("AliquotaIVA").text == "4.00"

    # Check DatiPagamento
    dati_pag = body.find("DatiPagamento")
    assert dati_pag is not None
    assert dati_pag.find("CondizioniPagamento").text == "TP01"
    rate_nodes = dati_pag.findall("DettaglioPagamento")
    assert len(rate_nodes) == 2
    assert rate_nodes[0].find("ImportoPagamento").text == "130.00"
    assert rate_nodes[0].find("DataScadenzaPagamento").text == "2026-11-30"

def test_generate_sdi_xml_reverse_charge_nature_n6(client, db_session):
    from services.sdi_service import generate_sdi_xml

    customer = Partner(
        ragione_sociale="Cliente Pallet Inadempiente",
        partita_iva="09876543210",
        codice_sdi="0000000",
        pec="cliente@pec.it",
        cap="40100",
        nazione="IT",
        tipo="cliente"
    )
    prod = Product(codice="IMB-EPAL", descrizione="Pallet EUR/EPAL", prezzo_vendita=18.0)
    db_session.add_all([customer, prod])
    db_session.commit()

    invoice = Invoice(
        numero=2,
        anno=2026,
        numero_completo="FT-2026-0002",
        tipo_documento="TD01",
        data_documento=date(2026, 10, 21),
        cliente_id=customer.id,
        totale_imponibile=180.0,
        totale_imposta=0.0,
        totale_fattura=180.0,
        castelletto_iva={"0": {"imponibile": 180.0, "imposta": 0.0}},
        note="Operazione in Reverse Charge ai sensi dell'Art. 74 comma 7/8 DPR 633/72 per cessione imballaggi usati.",
        stato="emessa"
    )
    db_session.add(invoice)
    db_session.commit()

    item = InvoiceItem(
        invoice_id=invoice.id,
        product_id=prod.id,
        descrizione="Cessione Pallet EUR/EPAL non restituiti ex L. 182/2025",
        quantita=10.0,
        prezzo_unitario=18.0,
        aliquota_iva=0,
        imponibile_riga=180.0
    )
    db_session.add(item)
    db_session.commit()

    xml_str, _ = generate_sdi_xml(invoice)
    root = ET.fromstring(xml_str)
    linea = root.find("FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee")
    assert linea.find("AliquotaIVA").text == "0.00"
    assert linea.find("Natura").text == "N6.7"

    riepilogo = root.find("FatturaElettronicaBody/DatiBeniServizi/DatiRiepilogo")
    assert riepilogo.find("Natura").text == "N6.7"

def test_api_sdi_validate_and_download_xml(client, db_session):
    admin_headers = {'X-Forwarded-Email': 'admin@company.com', 'X-Forwarded-Groups': 'admin'}
    client.get('/api/me', headers=admin_headers)

    customer = Partner(
        ragione_sociale="Natura Bio Srl",
        partita_iva="03456780999",
        codice_sdi="KRRH6B9",
        cap="40126",
        citta="Bologna",
        nazione="IT",
        tipo="cliente"
    )
    prod = Product(codice="ART-BIO-01", descrizione="Pasta Bio", prezzo_vendita=1.8)
    db_session.add_all([customer, prod])
    db_session.commit()
    c_id, p_id = customer.id, prod.id

    inv_res = client.post('/api/invoices', json={
        "cliente_id": c_id,
        "tipo_documento": "TD01",
        "items": [{"product_id": p_id, "quantita": 50, "prezzo_unitario": 1.8, "aliquota_iva": 4}]
    }, headers=admin_headers)
    assert inv_res.status_code == 201
    inv_id = inv_res.get_json()['id']

    val_res = client.get(f'/api/invoices/{inv_id}/sdi-validate', headers=admin_headers)
    assert val_res.status_code == 200
    val_data = val_res.get_json()
    assert val_data['valido'] is True
    assert val_data['codice_destinatario'] == "KRRH6B9"
    assert val_data['tipo_documento'] == "TD01"

    xml_res = client.get(f'/api/invoices/{inv_id}/xml', headers=admin_headers)
    assert xml_res.status_code == 200
    assert "application/xml" in xml_res.content_type
    assert "attachment" in xml_res.headers.get("Content-Disposition", "")
    assert "FatturaElettronica" in xml_res.data.decode('utf-8')
    assert "KRRH6B9" in xml_res.data.decode('utf-8')
