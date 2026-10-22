import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import date
from models import Invoice, Partner, DeliveryNote

DEFAULT_CEDENTE = {
    "paese": "IT",
    "partita_iva": "01234567890",
    "codice_fiscale": "01234567890",
    "denominazione": "ReteBio Società Cooperativa Agricola",
    "regime_fiscale": "RF01",
    "indirizzo": "Via della Cooperazione 12",
    "cap": "40100",
    "comune": "Bologna",
    "provincia": "BO",
    "nazione": "IT",
    "iban": "IT99C0123456789000000012345"
}

def determine_natura_iva(item, invoice):
    """Determina la natura IVA per operazioni ad aliquota zero"""
    note = (invoice.note or "").lower()
    if "reverse charge" in note or "inversione" in note or "182/2025" in note:
        return "N6.7" # Cessione imballaggi usati / recupero
    if invoice.cliente and invoice.cliente.nazione and invoice.cliente.nazione != 'IT':
        # UE o Extra UE
        ue_countries = {"AT", "BE", "BG", "CY", "HR", "DE", "DK", "ES", "EE", "FI", "FR", "GR", "IE", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "CZ", "RO", "SK", "SI", "SE", "HU"}
        if invoice.cliente.nazione.upper() in ue_countries:
            return "N3.2" # Cessioni intracomunitarie non imponibili
        return "N3.1" # Esportazioni extra UE
    return "N4" # Esenti ordinarie

def validate_sdi_invoice(invoice: Invoice) -> dict:
    """Esegue controlli formali di validità secondo le specifiche SDI FatturaPA"""
    errori = []
    avvisi = []

    cliente = invoice.cliente
    if not cliente:
        errori.append("Cliente destinatario mancante")
        return {"valido": False, "errori": errori, "avvisi": avvisi}

    if not cliente.ragione_sociale:
        errori.append("Denominazione/Ragione Sociale del cliente obbligatoria")

    piva = (cliente.partita_iva or "").strip()
    cf = (cliente.codice_fiscale or "").strip()
    if not piva and not cf:
        errori.append("Almeno uno tra Partita IVA e Codice Fiscale del cliente deve essere presente")

    sdi = (cliente.codice_sdi or "").strip()
    pec = (cliente.pec or "").strip()
    if not sdi:
        avvisi.append("Codice SDI non specificato, verrà impostato il codice generico '0000000'")
        sdi = "0000000"
    elif len(sdi) != 7 and sdi != "0000000":
        errori.append(f"Il Codice SDI deve essere composto esattamente da 7 caratteri (rilevato: '{sdi}')")

    if sdi == "0000000" and not pec:
        avvisi.append("Codice SDI generico 0000000 senza indirizzo PEC registrato")

    cap = (cliente.cap or "").strip()
    if not cap and (not cliente.nazione or cliente.nazione == 'IT'):
        errori.append("CAP del destinatario obbligatorio")

    # Controllo quadratura rate
    tot_rate = sum(inst.importo for inst in invoice.installments) if invoice.installments else 0.0
    if invoice.installments and abs(tot_rate - invoice.totale_fattura) > 0.01:
        errori.append(f"Discrepanza tra totale fattura ({invoice.totale_fattura:.2f} €) e totale rate ({tot_rate:.2f} €)")

    cedente_cf = DEFAULT_CEDENTE["codice_fiscale"]
    nome_file_previsto = f"IT{cedente_cf}_{invoice.numero:05d}.xml"

    return {
        "valido": len(errori) == 0,
        "errori": errori,
        "avvisi": avvisi,
        "codice_destinatario": sdi,
        "tipo_documento": invoice.tipo_documento or "TD01",
        "totale_documento": invoice.totale_fattura,
        "nome_file_previsto": nome_file_previsto
    }

def generate_sdi_xml(invoice: Invoice, cedente: dict = None) -> tuple[str, str]:
    """Genera l'XML conforme a FatturaPA v1.2.2 (FPR12) e restituisce (xml_string, filename)"""
    if cedente is None:
        cedente = DEFAULT_CEDENTE

    cliente = invoice.cliente
    validation = validate_sdi_invoice(invoice)
    if not validation["valido"]:
        raise ValueError("; ".join(validation["errori"]))

    codice_sdi = validation["codice_destinatario"]

    # ROOT
    root = ET.Element("p:FatturaElettronica", {
        "versione": "FPR12",
        "xmlns:ds": "http://www.w3.org/2000/09/xmldsig#",
        "xmlns:p": "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"
    })

    # ==========================================
    # 1. HEADER
    # ==========================================
    header = ET.SubElement(root, "FatturaElettronicaHeader")

    # 1.1 Dati Trasmissione
    dati_trasm = ET.SubElement(header, "DatiTrasmissione")
    id_trasm = ET.SubElement(dati_trasm, "IdTrasmittente")
    ET.SubElement(id_trasm, "IdPaese").text = cedente["paese"]
    ET.SubElement(id_trasm, "IdCodice").text = cedente["partita_iva"]
    ET.SubElement(dati_trasm, "ProgressivoInvio").text = f"{invoice.numero:05d}"
    ET.SubElement(dati_trasm, "FormatoTrasmissione").text = "FPR12"
    ET.SubElement(dati_trasm, "CodiceDestinatario").text = codice_sdi
    if codice_sdi == "0000000" and cliente.pec:
        ET.SubElement(dati_trasm, "PECDestinatario").text = cliente.pec

    # 1.2 Cedente Prestatore (ReteBio)
    ced_prest = ET.SubElement(header, "CedentePrestatore")
    dati_anag_ced = ET.SubElement(ced_prest, "DatiAnagrafici")
    id_fisc_ced = ET.SubElement(dati_anag_ced, "IdFiscaleIVA")
    ET.SubElement(id_fisc_ced, "IdPaese").text = cedente["paese"]
    ET.SubElement(id_fisc_ced, "IdCodice").text = cedente["partita_iva"]
    if cedente.get("codice_fiscale"):
        ET.SubElement(dati_anag_ced, "CodiceFiscale").text = cedente["codice_fiscale"]
    anag_ced = ET.SubElement(dati_anag_ced, "Anagrafica")
    ET.SubElement(anag_ced, "Denominazione").text = cedente["denominazione"]
    ET.SubElement(dati_anag_ced, "RegimeFiscale").text = cedente.get("regime_fiscale", "RF01")

    sede_ced = ET.SubElement(ced_prest, "Sede")
    ET.SubElement(sede_ced, "Indirizzo").text = cedente["indirizzo"]
    ET.SubElement(sede_ced, "CAP").text = cedente["cap"]
    ET.SubElement(sede_ced, "Comune").text = cedente["comune"]
    ET.SubElement(sede_ced, "Provincia").text = cedente["provincia"]
    ET.SubElement(sede_ced, "Nazione").text = cedente["nazione"]

    # 1.3 Cessionario Committente (Cliente)
    cess_comm = ET.SubElement(header, "CessionarioCommittente")
    dati_anag_cess = ET.SubElement(cess_comm, "DatiAnagrafici")
    if cliente.partita_iva:
        id_fisc_cess = ET.SubElement(dati_anag_cess, "IdFiscaleIVA")
        ET.SubElement(id_fisc_cess, "IdPaese").text = cliente.nazione or "IT"
        piva_clean = cliente.partita_iva.replace("IT", "").replace(" ", "").strip()
        ET.SubElement(id_fisc_cess, "IdCodice").text = piva_clean
    if cliente.codice_fiscale and not cliente.partita_iva:
        ET.SubElement(dati_anag_cess, "CodiceFiscale").text = cliente.codice_fiscale.strip()

    anag_cess = ET.SubElement(dati_anag_cess, "Anagrafica")
    ET.SubElement(anag_cess, "Denominazione").text = cliente.ragione_sociale

    sede_cess = ET.SubElement(cess_comm, "Sede")
    ET.SubElement(sede_cess, "Indirizzo").text = cliente.indirizzo or "N.D."
    ET.SubElement(sede_cess, "CAP").text = cliente.cap or "00000"
    ET.SubElement(sede_cess, "Comune").text = cliente.citta or "N.D."
    if cliente.provincia and len(cliente.provincia) == 2:
        ET.SubElement(sede_cess, "Provincia").text = cliente.provincia.upper()
    ET.SubElement(sede_cess, "Nazione").text = cliente.nazione or "IT"

    # ==========================================
    # 2. BODY
    # ==========================================
    body = ET.SubElement(root, "FatturaElettronicaBody")

    # 2.1 Dati Generali
    dati_gen = ET.SubElement(body, "DatiGenerali")
    dati_gen_doc = ET.SubElement(dati_gen, "DatiGeneraliDocumento")
    ET.SubElement(dati_gen_doc, "TipoDocumento").text = invoice.tipo_documento or "TD01"
    ET.SubElement(dati_gen_doc, "Divisa").text = "EUR"
    ET.SubElement(dati_gen_doc, "Data").text = invoice.data_documento.isoformat()
    ET.SubElement(dati_gen_doc, "Numero").text = invoice.numero_completo
    ET.SubElement(dati_gen_doc, "ImportoTotaleDocumento").text = f"{invoice.totale_fattura:.2f}"
    if invoice.note:
        # Tronca a 200 caratteri massimo da specifiche SDI
        ET.SubElement(dati_gen_doc, "Causale").text = invoice.note[:200]

    # Blocchi DatiDDT per fatture differite (TD24)
    ddt_grouped = {}
    for idx, it in enumerate(invoice.items):
        if it.delivery_note_id:
            ddt = it.delivery_note
            if not ddt:
                from models import db
                ddt = db.session.get(DeliveryNote, it.delivery_note_id)
            if ddt:
                if ddt.id not in ddt_grouped:
                    ddt_grouped[ddt.id] = {"ddt": ddt, "linee": []}
                ddt_grouped[ddt.id]["linee"].append(idx + 1)

    for ddt_info in ddt_grouped.values():
        ddt_obj = ddt_info["ddt"]
        dati_ddt = ET.SubElement(dati_gen, "DatiDDT")
        ET.SubElement(dati_ddt, "NumeroDDT").text = ddt_obj.numero_completo
        ET.SubElement(dati_ddt, "DataDDT").text = ddt_obj.data_documento.isoformat()
        for num_linea in ddt_info["linee"]:
            ET.SubElement(dati_ddt, "RiferimentoNumeroLinea").text = str(num_linea)

    # Blocchi DatiFattureCollegate per Note di Credito (TD04)
    if (invoice.tipo_documento == 'TD04' or invoice.invoice_origine_id) and invoice.invoice_origine_numero:
        dati_colleg = ET.SubElement(dati_gen, "DatiFattureCollegate")
        ET.SubElement(dati_colleg, "IdDocumento").text = invoice.invoice_origine_numero
        orig_date = invoice.invoice_origine.data_documento if invoice.invoice_origine else invoice.data_documento
        if orig_date:
            ET.SubElement(dati_colleg, "Data").text = orig_date.isoformat()

    # 2.2 Dati Beni e Servizi
    dati_beni = ET.SubElement(body, "DatiBeniServizi")
    nature_per_aliquota = {}

    for idx, it in enumerate(invoice.items):
        linea = ET.SubElement(dati_beni, "DettaglioLinee")
        ET.SubElement(linea, "NumeroLinea").text = str(idx + 1)
        ET.SubElement(linea, "Descrizione").text = it.descrizione or "Merce"
        ET.SubElement(linea, "Quantita").text = f"{float(it.quantita):.2f}"
        ET.SubElement(linea, "UnitaMisura").text = (it.unita_misura or "PZ")[:10]
        ET.SubElement(linea, "PrezzoUnitario").text = f"{float(it.prezzo_unitario):.4f}"
        ET.SubElement(linea, "PrezzoTotale").text = f"{float(it.imponibile_riga):.2f}"
        aliquota_val = float(it.aliquota_iva or 0)
        ET.SubElement(linea, "AliquotaIVA").text = f"{aliquota_val:.2f}"

        if aliquota_val == 0.0:
            natura_cod = determine_natura_iva(it, invoice)
            ET.SubElement(linea, "Natura").text = natura_cod
            nature_per_aliquota[0.0] = natura_cod

    # Dati Riepilogo IVA
    if invoice.castelletto_iva and isinstance(invoice.castelletto_iva, dict):
        for aliq_str, dati_iva in invoice.castelletto_iva.items():
            aliq_float = float(aliq_str)
            riepilogo = ET.SubElement(dati_beni, "DatiRiepilogo")
            ET.SubElement(riepilogo, "AliquotaIVA").text = f"{aliq_float:.2f}"
            if aliq_float == 0.0:
                riepilogo_natura = nature_per_aliquota.get(0.0) or determine_natura_iva(None, invoice)
                ET.SubElement(riepilogo, "Natura").text = riepilogo_natura
            ET.SubElement(riepilogo, "ImponibileImporto").text = f"{float(dati_iva.get('imponibile', 0.0)):.2f}"
            ET.SubElement(riepilogo, "Imposta").text = f"{float(dati_iva.get('imposta', 0.0)):.2f}"
            ET.SubElement(riepilogo, "EsigibilitaIVA").text = invoice.esigibilita_iva or "I"
    else:
        riepilogo = ET.SubElement(dati_beni, "DatiRiepilogo")
        ET.SubElement(riepilogo, "AliquotaIVA").text = "4.00"
        ET.SubElement(riepilogo, "ImponibileImporto").text = f"{invoice.totale_imponibile:.2f}"
        ET.SubElement(riepilogo, "Imposta").text = f"{invoice.totale_imposta:.2f}"
        ET.SubElement(riepilogo, "EsigibilitaIVA").text = invoice.esigibilita_iva or "I"

    # 2.3 Dati Pagamento
    if invoice.installments:
        dati_pag = ET.SubElement(body, "DatiPagamento")
        ET.SubElement(dati_pag, "CondizioniPagamento").text = "TP01" if len(invoice.installments) > 1 else "TP02"

        for inst in invoice.installments:
            dett_pag = ET.SubElement(dati_pag, "DettaglioPagamento")
            # Modalità bonifico bancario di default
            ET.SubElement(dett_pag, "ModalitaPagamento").text = "MP05"
            ET.SubElement(dett_pag, "DataScadenzaPagamento").text = inst.data_scadenza.isoformat()
            ET.SubElement(dett_pag, "ImportoPagamento").text = f"{float(inst.importo):.2f}"
            if cedente.get("iban"):
                ET.SubElement(dett_pag, "IBAN").text = cedente["iban"]

    # Formattazione Pretty XML
    xml_raw = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(xml_raw)
    xml_pretty = parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")

    filename = f"IT{cedente['codice_fiscale']}_{invoice.numero:05d}.xml"
    return xml_pretty, filename
