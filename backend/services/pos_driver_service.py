import os
import socket
from datetime import datetime

class PosDriverService:
    @staticmethod
    def print_ticket(sale, station) -> dict:
        driver = (station.driver_tipo or 'simulator').lower()
        if driver == 'simulator':
            return PosDriverService._execute_simulator(sale, station)
        elif driver == 'epson_epos_http':
            return PosDriverService._execute_epson_http(sale, station)
        elif driver == 'custom_tcp':
            return PosDriverService._execute_custom_tcp(sale, station)
        else:
            return PosDriverService._execute_simulator(sale, station)

    @staticmethod
    def _execute_simulator(sale, station) -> dict:
        ticket_lines = []
        ticket_lines.append("=" * 36)
        intestazione = station.intestazione or "RETEBIO SOCIETA' AGRICOLA\nBOLOGNA (BO)"
        for line in intestazione.strip().split("\n"):
            ticket_lines.append(f"{line.center(36)}")
        ticket_lines.append("-" * 36)
        data_str = sale.data_ora.strftime('%d/%m/%Y %H:%M:%S') if sale.data_ora else datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')
        ticket_lines.append(f"DOCUMENTO COMMERCIALE N. {sale.numero_scontrino}")
        ticket_lines.append(f"Data: {data_str}")
        ticket_lines.append(f"Cassa: {station.codice} - {station.nome}")
        ticket_lines.append("-" * 36)

        for item in sale.items:
            desc = item.product.descrizione if item.product else 'Articolo'
            ticket_lines.append(f"{desc[:36]}")
            qty_price = f"{float(item.quantita):.2f} x {float(item.prezzo_unitario):.2f}"
            subtot = f"{float(item.subtotale):.2f}"
            ticket_lines.append(f"  {qty_price:<20} {subtot:>12} (IVA {int(item.aliquota_iva)}%)")
            if item.lotto:
                scad_str = f" Scad: {item.data_scadenza.strftime('%d/%m/%Y')}" if item.data_scadenza else ""
                ticket_lines.append(f"  [Lotto: {item.lotto}{scad_str}]")

        ticket_lines.append("-" * 36)
        tot_lordo = f"{float(sale.totale_lordo):.2f}"
        tot_imp = f"{float(sale.totale_imponibile):.2f}"
        tot_iva = f"{float(sale.totale_iva):.2f}"
        ticket_lines.append(f"TOTALE COMPLESSIVO:          EUR {tot_lordo:>7}")
        ticket_lines.append(f"di cui Imponibile: EUR {tot_imp:>6} | IVA: EUR {tot_iva:>5}")
        ticket_lines.append("-" * 36)
        pag_tipo = (sale.metodo_pagamento or 'contanti').upper()
        pagato = f"{float(sale.importo_pagato):.2f}"
        resto = f"{float(sale.importo_resto):.2f}"
        ticket_lines.append(f"PAGAMENTO {pag_tipo:<12} EUR {pagato:>7}")
        if float(sale.importo_resto) > 0:
            ticket_lines.append(f"RESTO:                       EUR {resto:>7}")
        ticket_lines.append("-" * 36)
        matr = station.matricola_rt or "RT-SIM-001"
        ticket_lines.append(f"MATRICOLA RT: {matr}")
        pie = station.pie_pagina or "ARRIVEDERCI E GRAZIE"
        ticket_lines.append(f"{pie.center(36)}")
        ticket_lines.append("=" * 36)

        ticket_ascii = "\n".join(ticket_lines)
        return {
            "success": True,
            "stato_fiscale": "simulato",
            "messaggio": f"Scontrino {sale.numero_scontrino} emesso con successo dal simulatore",
            "ticket_ascii": ticket_ascii
        }

    @staticmethod
    def _execute_epson_http(sale, station) -> dict:
        sim = PosDriverService._execute_simulator(sale, station)
        if not station.ip_address:
            sim["stato_fiscale"] = "simulato"
            return sim
        try:
            import urllib.request
            xml_data = f"""<epos-print xmlns="http://www.epson-pos.com/schemas/2011/03/epos-print">
<text>{sale.numero_scontrino} Totale: {sale.totale_lordo}&#10;</text>
<cut/>
</epos-print>""".encode('utf-8')
            url = f"http://{station.ip_address}:{station.porta}/cgi-bin/fpmate.cgi"
            req = urllib.request.Request(url, data=xml_data, headers={'Content-Type': 'text/xml; charset=utf-8'})
            with urllib.request.urlopen(req, timeout=1) as resp:
                sim["stato_fiscale"] = "stampato"
                sim["dettaglio"] = f"Inviato a Epson RT su {url}"
                return sim
        except Exception as e:
            sim["stato_fiscale"] = "errore"
            sim["messaggio"] = f"Cassa Epson non raggiungibile: {str(e)} (generato layout scontrino)"
            return sim

    @staticmethod
    def _execute_custom_tcp(sale, station) -> dict:
        sim = PosDriverService._execute_simulator(sale, station)
        if not station.ip_address:
            return sim
        try:
            with socket.create_connection((station.ip_address, station.porta), timeout=1) as s:
                cmd = f"CLEAR\nSALE {sale.totale_lordo}\nCLOSE\n".encode('ascii')
                s.sendall(cmd)
                sim["stato_fiscale"] = "stampato"
                return sim
        except Exception as e:
            sim["stato_fiscale"] = "errore"
            sim["messaggio"] = f"Cassa Custom TCP non raggiungibile: {str(e)}"
            return sim
