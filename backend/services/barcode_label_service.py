import re
import html

def safe_float(val, default=0.0):
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (ValueError, TypeError):
        return default

# Tabella dei pattern per Code 128 (valori da 0 a 106)
# Ciascun pattern definisce le 6 larghezze modulari alternate (barra, spazio, barra, spazio, barra, spazio)
CODE128_PATTERNS = [
    (2, 1, 2, 2, 2, 2), (2, 2, 2, 1, 2, 2), (2, 2, 2, 2, 2, 1), (1, 2, 1, 2, 2, 3), (1, 2, 1, 3, 2, 2),
    (1, 3, 1, 2, 2, 2), (1, 2, 2, 2, 1, 3), (1, 2, 2, 3, 1, 2), (1, 3, 2, 2, 1, 2), (2, 2, 1, 2, 1, 3),
    (2, 2, 1, 3, 1, 2), (2, 3, 1, 2, 1, 2), (1, 1, 2, 2, 3, 2), (1, 2, 2, 1, 3, 2), (1, 2, 2, 2, 3, 1),
    (1, 1, 3, 2, 2, 2), (1, 2, 3, 1, 2, 2), (1, 2, 3, 2, 2, 1), (2, 2, 3, 2, 1, 1), (2, 2, 1, 1, 3, 2),
    (2, 2, 1, 2, 3, 1), (2, 1, 3, 2, 1, 2), (2, 2, 3, 1, 1, 2), (3, 1, 2, 1, 3, 1), (3, 1, 1, 2, 2, 2),
    (3, 2, 1, 1, 2, 2), (3, 2, 1, 2, 2, 1), (3, 1, 2, 2, 1, 2), (3, 2, 2, 1, 1, 2), (3, 2, 2, 2, 1, 1),
    (2, 1, 2, 1, 2, 3), (2, 1, 2, 3, 2, 1), (2, 3, 2, 1, 2, 1), (1, 1, 1, 3, 2, 3), (1, 3, 1, 1, 2, 3),
    (1, 3, 1, 3, 2, 1), (1, 1, 2, 3, 1, 3), (1, 3, 2, 1, 1, 3), (1, 3, 2, 3, 1, 1), (2, 1, 1, 3, 1, 3),
    (2, 3, 1, 1, 1, 3), (2, 3, 1, 3, 1, 1), (1, 1, 2, 1, 3, 3), (1, 1, 2, 3, 3, 1), (1, 3, 2, 1, 3, 1),
    (1, 1, 3, 1, 2, 3), (1, 1, 3, 3, 2, 1), (1, 3, 3, 1, 2, 1), (3, 1, 3, 1, 2, 1), (2, 1, 1, 3, 3, 1),
    (2, 3, 1, 1, 3, 1), (2, 1, 3, 1, 1, 3), (2, 1, 3, 3, 1, 1), (2, 1, 3, 1, 3, 1), (3, 1, 1, 1, 2, 3),
    (3, 1, 1, 3, 2, 1), (3, 3, 1, 1, 2, 1), (3, 1, 2, 1, 1, 3), (3, 1, 2, 3, 1, 1), (3, 3, 2, 1, 1, 1),
    (3, 1, 4, 1, 1, 1), (2, 2, 1, 4, 1, 1), (4, 3, 1, 1, 1, 1), (1, 1, 1, 2, 2, 4), (1, 1, 1, 4, 2, 2),
    (1, 2, 1, 1, 2, 4), (1, 2, 1, 4, 2, 1), (1, 4, 1, 1, 2, 2), (1, 4, 1, 2, 2, 1), (1, 1, 2, 2, 1, 4),
    (1, 1, 2, 4, 1, 2), (1, 2, 2, 1, 1, 4), (1, 2, 2, 4, 1, 1), (1, 4, 2, 1, 1, 2), (1, 4, 2, 2, 1, 1),
    (2, 4, 1, 2, 1, 1), (2, 2, 1, 1, 1, 4), (4, 1, 3, 1, 1, 1), (2, 4, 1, 1, 1, 2), (1, 3, 4, 1, 1, 1),
    (1, 1, 1, 2, 4, 2), (1, 2, 1, 1, 4, 2), (1, 2, 1, 2, 4, 1), (1, 1, 4, 2, 1, 2), (1, 2, 4, 1, 1, 2),
    (1, 2, 4, 2, 1, 1), (4, 1, 1, 2, 1, 2), (4, 2, 1, 1, 1, 2), (4, 2, 1, 2, 1, 1), (2, 1, 2, 1, 4, 1),
    (2, 1, 4, 1, 2, 1), (4, 1, 2, 1, 2, 1), (1, 1, 1, 1, 4, 3), (1, 1, 1, 3, 4, 1), (1, 3, 1, 1, 4, 1),
    (1, 1, 4, 1, 1, 3), (1, 1, 4, 3, 1, 1), (4, 1, 1, 1, 1, 3), (4, 1, 1, 3, 1, 1), (1, 1, 3, 1, 4, 1),
    (1, 1, 4, 1, 3, 1), (3, 1, 1, 1, 4, 1), (4, 1, 1, 1, 3, 1), (2, 1, 1, 4, 1, 2), (2, 1, 1, 2, 1, 4),
    (2, 1, 1, 2, 3, 2), # 104: Start B
    (2, 3, 3, 1, 1, 1, 2) # 106: Stop (7 larghezze)
]

START_B = 104
STOP = 106

class BarcodeLabelService:
    @staticmethod
    def generate_code128_svg(code: str, height: int = 55, bar_width: int = 2) -> str:
        """
        Genera codice a barre SVG conforme Code 128 (Subset B)
        """
        if not code:
            code = "000000"

        # Conversione caratteri ASCII (da 32 a 126 hanno codice = ord(c) - 32)
        values = [START_B]
        for ch in code:
            val = ord(ch) - 32
            if 0 <= val <= 95:
                values.append(val)
            else:
                values.append(0)

        # Calcolo Checksum modulo 103
        checksum = values[0]
        for i, val in enumerate(values[1:], start=1):
            checksum += i * val
        checksum %= 103
        values.append(checksum)
        values.append(STOP)

        # Tracciamento coordinate barre e spazi
        rects = []
        x = 10 # Margine sinistro (quiet zone)

        for val in values:
            pattern = CODE128_PATTERNS[val]
            is_bar = True
            for w in pattern:
                w_px = w * bar_width
                if is_bar:
                    rects.append(f'<rect x="{x}" y="0" width="{w_px}" height="{height}" fill="black" />')
                x += w_px
                is_bar = not is_bar

        total_width = x + 10 # Margine destro
        total_height = height + 18

        svg_content = "\n  ".join(rects)
        escaped_code = html.escape(code)
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_width} {total_height}" width="{total_width}" height="{total_height}">
  <style>
    .barcode-text {{ font-family: monospace; font-size: 13px; font-weight: bold; fill: #000; text-anchor: middle; }}
  </style>
  {svg_content}
  <text x="{total_width / 2:.1f}" y="{height + 14}" class="barcode-text">{escaped_code}</text>
</svg>"""
        return svg

    @staticmethod
    def generate_pallet_zpl(data: dict) -> str:
        """
        Genera comandi ZPL II per etichetta bancale standard (100x150 mm @ 203 DPI = 800x1200 dots)
        """
        desc = (data.get("descrizione") or "PRODOTTO BIOLOGICO")[:36]
        codice = (data.get("codice_articolo") or "ART-BIO").upper()
        lotto = (data.get("lotto") or "LOTTO-DEFAULT").upper()
        scad = data.get("data_scadenza") or "N.D."
        origine = (data.get("origine") or "ITALIA").upper()
        ente = (data.get("ente_certificatore") or "IT-BIO-009 CCPB").upper()
        colli = int(safe_float(data.get("colli"), 0))
        p_netto = safe_float(data.get("peso_netto"), 0.0)
        p_lordo = safe_float(data.get("peso_lordo"), p_netto + 25.0)
        tara = safe_float(data.get("tara"), 25.0)

        barcode_val = f"{codice}-{lotto}".replace(" ", "")

        zpl = f"""^XA
^CI28
^PW800
^LL1200
^FO40,40^A0N,40,40^FDRETEBIO SOCIETA' AGRICOLA^FS
^FO40,85^A0N,26,26^FDOperatore Controllato: {ente}^FS
^FO40,120^GB720,3,3^FS
^FO40,140^A0N,30,30^FDCODICE ARTICOLO: {codice}^FS
^FO40,180^A0N,46,46^FD{desc}^FS
^FO40,240^GB720,3,3^FS
^FO40,260^A0N,38,38^FDLOTTO: {lotto}^FS
^FO420,260^A0N,38,38^FDSCADENZA: {scad}^FS
^FO40,310^A0N,32,32^FDORIGINE: {origine}^FS
^FO40,355^GB720,3,3^FS
^FO40,375^A0N,35,35^FDCOLLI: {colli}^FS
^FO280,375^A0N,35,35^FDTARA: {tara:.1f} kg^FS
^FO520,375^A0N,35,35^FDNETTO: {p_netto:.1f} kg^FS
^FO40,425^A0N,44,44^FDPESO LORDO: {p_lordo:.1f} kg^FS
^FO40,480^GB720,3,3^FS
^FO100,520^BY3,3,140^BCN,140,Y,N,N^FD{barcode_val}^FS
^FO40,710^GB720,3,3^FS
^FO40,730^A0N,24,24^FDTracciabilita Biologica Reg. (UE) 2018/848 - GS1-128 SSCC^FS
^XZ"""
        return zpl

    @staticmethod
    def generate_collo_zpl(data: dict) -> str:
        """
        Genera comandi ZPL II per etichetta cassetta/collo (50x30 mm @ 203 DPI = 400x240 dots)
        """
        desc = (data.get("descrizione") or "PROD BIO")[:22]
        codice = (data.get("codice_articolo") or "ART").upper()
        lotto = (data.get("lotto") or "LOTTO").upper()
        scad = data.get("data_scadenza") or "N.D."
        p_netto = safe_float(data.get("peso_netto"), 0.0)

        barcode_val = f"{codice}-{lotto}".replace(" ", "")

        zpl = f"""^XA
^CI28
^PW400
^LL240
^FO20,20^A0N,26,26^FD{desc}^FS
^FO20,52^A0N,20,20^FDLOTTO: {lotto}^FS
^FO220,52^A0N,20,20^FDSCAD: {scad}^FS
^FO20,78^A0N,20,20^FDPESO NETTO: {p_netto:.1f} kg^FS
^FO30,108^BY2,2,75^BCN,75,Y,N,N^FD{barcode_val}^FS
^XZ"""
        return zpl

    @staticmethod
    def render_pallet_html(data: dict) -> str:
        """
        Genera template HTML vettoriale per anteprima e stampa termica 100x150 mm
        """
        desc = data.get("descrizione") or "Prodotto Biologico"
        codice = data.get("codice_articolo") or "ART-BIO"
        lotto = data.get("lotto") or "N.D."
        scad = data.get("data_scadenza") or "N.D."
        origine = data.get("origine") or "Italia"
        ente = data.get("ente_certificatore") or "IT-BIO-009 CCPB"
        colli = int(safe_float(data.get("colli"), 0))
        p_netto = safe_float(data.get("peso_netto"), 0.0)
        p_lordo = safe_float(data.get("peso_lordo"), p_netto + 25.0)
        tara = safe_float(data.get("tara"), 25.0)

        barcode_val = f"{codice}-{lotto}".replace(" ", "")
        svg = BarcodeLabelService.generate_code128_svg(barcode_val, height=60, bar_width=2)

        return f"""<div class="pallet-label" style="width: 100mm; min-height: 145mm; border: 2px solid #000; padding: 5mm; font-family: 'Helvetica Neue', Arial, sans-serif; background: #fff; box-sizing: border-box; color: #000;">
  <div style="border-bottom: 2px solid #000; padding-bottom: 2mm; margin-bottom: 2mm;">
    <div style="font-size: 16px; font-weight: bold; text-transform: uppercase;">RETEBIO SOCIETÀ AGRICOLA</div>
    <div style="font-size: 11px; color: #2e7d32; font-weight: bold;">OPERATORE CONTROLLATO: {ente}</div>
  </div>

  <div style="border-bottom: 2px solid #000; padding-bottom: 3mm; margin-bottom: 3mm;">
    <div style="font-size: 11px; font-weight: bold; color: #555;">CODICE: {codice}</div>
    <div style="font-size: 20px; font-weight: 900; text-transform: uppercase; line-height: 1.1;">{desc}</div>
  </div>

  <div style="display: flex; justify-content: space-between; border-bottom: 2px solid #000; padding-bottom: 2mm; margin-bottom: 2mm;">
    <div>
      <div style="font-size: 10px; color: #555;">LOTTO BIOLOGICO</div>
      <div style="font-size: 17px; font-weight: bold;">{lotto}</div>
    </div>
    <div style="text-align: right;">
      <div style="font-size: 10px; color: #555;">SCADENZA</div>
      <div style="font-size: 16px; font-weight: bold;">{scad}</div>
    </div>
  </div>

  <div style="border-bottom: 2px solid #000; padding-bottom: 2mm; margin-bottom: 2mm; font-size: 13px; font-weight: bold;">
    ORIGINE: {origine.upper()}
  </div>

  <div style="display: flex; justify-content: space-between; border-bottom: 2px solid #000; padding-bottom: 2mm; margin-bottom: 3mm; font-size: 14px;">
    <div><strong>Colli:</strong> {colli}</div>
    <div><strong>Tara:</strong> {tara:.1f} kg</div>
    <div><strong>Netto:</strong> {p_netto:.1f} kg</div>
  </div>

  <div style="font-size: 18px; font-weight: bold; margin-bottom: 3mm;">
    PESO LORDO TOTALE: {p_lordo:.1f} kg
  </div>

  <div style="text-align: center; margin: 3mm 0;">
    {svg}
  </div>

  <div style="border-top: 1px solid #777; padding-top: 1mm; font-size: 9px; text-align: center; color: #444;">
    Tracciabilità di Filiera Biologica Reg. (UE) 2018/848 - GS1-128 SSCC
  </div>
</div>"""

    @staticmethod
    def render_collo_html(data: dict) -> str:
        """
        Genera template HTML per etichetta collo compatto 50x30 mm
        """
        desc = data.get("descrizione") or "Prod Bio"
        codice = data.get("codice_articolo") or "ART"
        lotto = data.get("lotto") or "N.D."
        scad = data.get("data_scadenza") or "N.D."
        p_netto = safe_float(data.get("peso_netto"), 0.0)

        barcode_val = f"{codice}-{lotto}".replace(" ", "")
        svg = BarcodeLabelService.generate_code128_svg(barcode_val, height=35, bar_width=1)

        return f"""<div class="collo-label" style="width: 50mm; height: 30mm; border: 1px solid #000; padding: 2mm; font-family: Arial, sans-serif; background: #fff; box-sizing: border-box;">
  <div style="font-size: 10px; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{desc}</div>
  <div style="display: flex; justify-content: space-between; font-size: 8px; margin: 1mm 0;">
    <span>LOT: {lotto}</span>
    <span>SCAD: {scad}</span>
    <span>{p_netto:.1f} kg</span>
  </div>
  <div style="text-align: center;">
    {svg}
  </div>
</div>"""

    @classmethod
    def generate_label(
        cls,
        sku: str,
        description: str,
        lot: str,
        expiry_date: str = None,
        quantity: float = 1.0,
        weight_net: float = 0.0,
        unit: str = "KG",
        document_ref: str = "",
        recipient_name: str = "",
        layout: str = "pallet"
    ) -> dict:
        layout_str = (layout or "pallet").lower()
        data = {
            "descrizione": description or "Articolo Bio",
            "codice_articolo": sku or "ART-BIO",
            "lotto": lot or "L-00",
            "data_scadenza": expiry_date,
            "colli": int(quantity or 1),
            "peso_netto": float(weight_net or quantity or 0.0),
            "peso_lordo": float(weight_net or quantity or 0.0) + (25.0 if layout_str == "pallet" else 0.5),
            "tara": 25.0 if layout_str == "pallet" else 0.5,
            "origine": "Italia",
            "ente_certificatore": "IT-BIO-009 CCPB",
            "documento_rif": document_ref,
            "destinatario": recipient_name
        }
        barcode_val = f"{data['codice_articolo']}-{data['lotto']}".replace(" ", "")

        if layout_str == "pallet":
            zpl = cls.generate_pallet_zpl(data)
            html = cls.render_pallet_html(data)
            svg = cls.generate_code128_svg(barcode_val, height=60, bar_width=2)
        else:
            zpl = cls.generate_collo_zpl(data)
            html = cls.render_collo_html(data)
            svg = cls.generate_code128_svg(barcode_val, height=35, bar_width=1)

        return {
            "sku": sku,
            "lot": lot,
            "label_type": layout_str,
            "barcode_value": barcode_val,
            "zpl": zpl,
            "svg_barcode": svg,
            "html_preview": html,
            "dati": data
        }
