from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from models import User
from api.deps import require_auth
from services.barcode_label_service import BarcodeLabelService

router = APIRouter(prefix="/api/labels", tags=["Labels"])

@router.post("/generate")
async def generate_label(
    request: Request,
    current_user: User = Depends(require_auth())
):
    data = await request.json() or {}
    label_type = (data.get('label_type') or 'pallet').lower()

    codice = data.get('codice_articolo') or 'ART'
    lotto = data.get('lotto') or '001'
    barcode_val = f"{codice}-{lotto}".replace(" ", "")

    if label_type == 'pallet':
        zpl = BarcodeLabelService.generate_pallet_zpl(data)
        html = BarcodeLabelService.render_pallet_html(data)
        svg = BarcodeLabelService.generate_code128_svg(barcode_val, height=60, bar_width=2)
    else:
        zpl = BarcodeLabelService.generate_collo_zpl(data)
        html = BarcodeLabelService.render_collo_html(data)
        svg = BarcodeLabelService.generate_code128_svg(barcode_val, height=35, bar_width=1)

    return {
        "label_type": label_type,
        "barcode_value": barcode_val,
        "zpl": zpl,
        "svg_barcode": svg,
        "html_preview": html
    }
