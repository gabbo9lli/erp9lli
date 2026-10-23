from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
import calendar
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from models import (
    Invoice, InvoiceItem, InvoiceInstallment, DeliveryNote,
    Partner, Product, PurchaseDeliveryNote, PurchaseDeliveryNoteItem
)
from services.event_dispatcher import dispatch_event
from services.accounting_service import AccountingService

class InvoiceService:
    @staticmethod
    def get_next_invoice_number(db: Session, anno: int) -> int:
        max_num = db.query(func.max(Invoice.numero)).filter(
            Invoice.anno == anno,
            Invoice.tipo_documento != 'TD04'
        ).scalar()
        return (max_num or 0) + 1

    @staticmethod
    def get_next_credit_note_number(db: Session, anno: int) -> int:
        max_num = db.query(func.max(Invoice.numero)).filter(
            Invoice.anno == anno,
            Invoice.tipo_documento == 'TD04'
        ).scalar()
        return (max_num or 0) + 1

    @staticmethod
    def calculate_installments(totale_fattura: float, data_documento: date, condizioni: Optional[str]) -> list:
        cond = (condizioni or '30gg fm').lower()
        if '30/60/90' in cond:
            giorni_lista = [30, 60, 90]
        elif '30/60' in cond:
            giorni_lista = [30, 60]
        elif '60/90' in cond:
            giorni_lista = [60, 90]
        elif '60' in cond:
            giorni_lista = [60]
        elif '90' in cond:
            giorni_lista = [90]
        elif 'vista' in cond or 'contanti' in cond or 'immediato' in cond:
            giorni_lista = [0]
        else:
            giorni_lista = [30]

        totale_rate = len(giorni_lista)
        base_importo = round(totale_fattura / totale_rate, 2)
        rate = []
        somma_rate = 0.0

        for idx, giorni in enumerate(giorni_lista):
            if giorni == 0:
                scadenza = data_documento
            elif 'fm' in cond or 'fine mese' in cond:
                target_date = data_documento + timedelta(days=giorni)
                _, last_day = calendar.monthrange(target_date.year, target_date.month)
                scadenza = date(target_date.year, target_date.month, last_day)
            else:
                scadenza = data_documento + timedelta(days=giorni)

            if idx == totale_rate - 1:
                importo_rata = round(totale_fattura - somma_rate, 2)
            else:
                importo_rata = base_importo
                somma_rate += importo_rata

            rate.append({
                "numero_rata": idx + 1,
                "totale_rate": totale_rate,
                "data_scadenza": scadenza,
                "importo": importo_rata,
                "stato": "aperta"
            })
        return rate

    @classmethod
    def create_invoice_from_ddt(cls, db: Session, data: dict) -> Invoice:
        cliente_id = data.get('cliente_id')
        ddt_ids = data.get('ddt_ids', [])
        if not cliente_id or not ddt_ids:
            raise HTTPException(status_code=400, detail="cliente_id e ddt_ids sono obbligatori")

        cliente = db.get(Partner, cliente_id)
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente non trovato")

        ddts = db.query(DeliveryNote).filter(DeliveryNote.id.in_(ddt_ids)).all()
        if len(ddts) != len(ddt_ids):
            raise HTTPException(status_code=404, detail="Uno o più DDT non trovati")

        for d in ddts:
            if d.cliente_id != cliente.id:
                raise HTTPException(status_code=400, detail=f"DDT {d.numero_completo} non appartiene a questo cliente")
            if d.stato != 'confermato':
                raise HTTPException(status_code=400, detail=f"DDT {d.numero_completo} non è in stato confermato (stato: {d.stato})")

        doc_date_str = data.get('data_documento')
        doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()
        anno = doc_date.year
        numero = cls.get_next_invoice_number(db, anno)
        numero_completo = f"FT-{anno}-{numero:04d}"

        condizioni = data.get('condizioni_pagamento', cliente.condizioni_pagamento or '30gg fm')

        totale_imponibile = 0.0
        totale_imposta = 0.0
        castelletto = {}
        invoice_items = []

        for ddt in ddts:
            for item in ddt.items:
                imp_riga = round(item.quantita * item.prezzo_unitario, 2)
                iva_riga = round(imp_riga * (item.aliquota_iva / 100.0), 2)
                totale_imponibile += imp_riga
                totale_imposta += iva_riga

                aliquota_key = str(item.aliquota_iva)
                if aliquota_key not in castelletto:
                    castelletto[aliquota_key] = {"imponibile": 0.0, "imposta": 0.0}
                castelletto[aliquota_key]["imponibile"] = round(castelletto[aliquota_key]["imponibile"] + imp_riga, 2)
                castelletto[aliquota_key]["imposta"] = round(castelletto[aliquota_key]["imposta"] + iva_riga, 2)

                inv_item = InvoiceItem(
                    delivery_note_id=ddt.id,
                    product_id=item.product_id,
                    descrizione=item.descrizione,
                    unita_misura=item.unita_misura,
                    colli=item.colli,
                    quantita=item.quantita,
                    prezzo_unitario=item.prezzo_unitario,
                    aliquota_iva=item.aliquota_iva,
                    imponibile_riga=imp_riga,
                    lotto=item.lotto,
                    data_scadenza=item.data_scadenza
                )
                invoice_items.append(inv_item)

        totale_imponibile = round(totale_imponibile, 2)
        totale_imposta = round(totale_imposta, 2)
        totale_fattura = round(totale_imponibile + totale_imposta, 2)

        rate_data = cls.calculate_installments(totale_fattura, doc_date, condizioni)
        installments = [
            InvoiceInstallment(
                numero_rata=r["numero_rata"],
                totale_rate=r["totale_rate"],
                data_scadenza=r["data_scadenza"],
                importo=r["importo"],
                stato="aperta"
            ) for r in rate_data
        ]

        invoice = Invoice(
            numero=numero,
            anno=anno,
            numero_completo=numero_completo,
            tipo_documento='TD24',
            data_documento=doc_date,
            cliente_id=cliente.id,
            condizioni_pagamento=condizioni,
            esigibilita_iva=data.get('esigibilita_iva', 'I'),
            totale_imponibile=totale_imponibile,
            totale_imposta=totale_imposta,
            totale_fattura=totale_fattura,
            castelletto_iva=castelletto,
            stato='emessa',
            note=data.get('note'),
            items=invoice_items,
            installments=installments
        )
        db.add(invoice)

        for ddt in ddts:
            ddt.stato = 'fatturato'
            ddt.invoice_id = invoice.id

        db.flush()
        je = AccountingService.auto_post_invoice_to_accounting(db, invoice)
        try:
            dispatch_event(
                event_type_code="EMISSIONE_FATTURA",
                titolo=f"Fattura {invoice.numero_completo}",
                descrizione=f"Emessa fattura differita {invoice.numero_completo} - Totale {invoice.totale_fattura:.2f} €",
                entita_tipo="invoice",
                entita_id=invoice.id,
                partner_id=invoice.cliente_id,
                payload_dati={"totale": float(invoice.totale_fattura), "journal_entry_id": je.id if je else None},
                db=db
            )
        except Exception:
            pass

        try:
            db.commit()
            db.refresh(invoice)
            return invoice
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    @classmethod
    def create_invoice_direct(cls, db: Session, data: dict) -> Invoice:
        cliente_id = data.get('cliente_id')
        if not cliente_id:
            raise HTTPException(status_code=400, detail="cliente_id is required")

        cliente = db.get(Partner, cliente_id)
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente non trovato")

        items_data = data.get('items', [])
        if not items_data:
            raise HTTPException(status_code=400, detail="At least one item is required")

        doc_date_str = data.get('data_documento')
        doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()
        anno = doc_date.year
        numero = cls.get_next_invoice_number(db, anno)
        numero_completo = f"FT-{anno}-{numero:04d}"

        condizioni = data.get('condizioni_pagamento', cliente.condizioni_pagamento or '30gg fm')

        totale_imponibile = 0.0
        totale_imposta = 0.0
        castelletto = {}
        invoice_items = []

        for item in items_data:
            prod_id = item.get('product_id')
            product = db.get(Product, prod_id) if prod_id else None
            descrizione = item.get('descrizione', product.descrizione if product else 'Articolo')
            unita_misura = item.get('unita_misura', product.unita_misura if product else 'KG')
            colli = int(item.get('colli', 1))
            quantita = float(item.get('quantita', 1.0))
            prezzo_unitario = float(item.get('prezzo_unitario', product.prezzo_vendita if product else 0.0))
            aliquota_iva = int(item.get('aliquota_iva', product.aliquota_iva if product else 4))

            imp_riga = round(quantita * prezzo_unitario, 2)
            iva_riga = round(imp_riga * (aliquota_iva / 100.0), 2)
            totale_imponibile += imp_riga
            totale_imposta += iva_riga

            aliquota_key = str(aliquota_iva)
            if aliquota_key not in castelletto:
                castelletto[aliquota_key] = {"imponibile": 0.0, "imposta": 0.0}
            castelletto[aliquota_key]["imponibile"] = round(castelletto[aliquota_key]["imponibile"] + imp_riga, 2)
            castelletto[aliquota_key]["imposta"] = round(castelletto[aliquota_key]["imposta"] + iva_riga, 2)

            data_scad_val = None
            if item.get('data_scadenza'):
                if isinstance(item['data_scadenza'], str):
                    data_scad_val = datetime.strptime(item['data_scadenza'], '%Y-%m-%d').date()
                else:
                    data_scad_val = item['data_scadenza']

            inv_item = InvoiceItem(
                product_id=prod_id,
                descrizione=descrizione,
                unita_misura=unita_misura,
                colli=colli,
                quantita=quantita,
                prezzo_unitario=prezzo_unitario,
                aliquota_iva=aliquota_iva,
                imponibile_riga=imp_riga,
                lotto=item.get('lotto'),
                data_scadenza=data_scad_val
            )
            invoice_items.append(inv_item)

        totale_imponibile = round(totale_imponibile, 2)
        totale_imposta = round(totale_imposta, 2)
        totale_fattura = round(totale_imponibile + totale_imposta, 2)

        rate_data = cls.calculate_installments(totale_fattura, doc_date, condizioni)
        installments = [
            InvoiceInstallment(
                numero_rata=r["numero_rata"],
                totale_rate=r["totale_rate"],
                data_scadenza=r["data_scadenza"],
                importo=r["importo"],
                stato="aperta"
            ) for r in rate_data
        ]

        invoice = Invoice(
            numero=numero,
            anno=anno,
            numero_completo=numero_completo,
            tipo_documento=data.get('tipo_documento', 'TD01'),
            data_documento=doc_date,
            cliente_id=cliente.id,
            condizioni_pagamento=condizioni,
            esigibilita_iva=data.get('esigibilita_iva', 'I'),
            totale_imponibile=totale_imponibile,
            totale_imposta=totale_imposta,
            totale_fattura=totale_fattura,
            castelletto_iva=castelletto,
            stato='emessa',
            note=data.get('note'),
            items=invoice_items,
            installments=installments
        )
        db.add(invoice)
        db.flush()
        je = AccountingService.auto_post_invoice_to_accounting(db, invoice)
        try:
            dispatch_event(
                event_type_code="EMISSIONE_FATTURA",
                titolo=f"Fattura {invoice.numero_completo}",
                descrizione=f"Emessa fattura {invoice.numero_completo} ({invoice.tipo_documento}) - Totale {invoice.totale_fattura:.2f} €",
                entita_tipo="invoice",
                entita_id=invoice.id,
                partner_id=invoice.cliente_id,
                payload_dati={"totale": float(invoice.totale_fattura), "journal_entry_id": je.id if je else None},
                db=db
            )
        except Exception:
            pass

        try:
            db.commit()
            db.refresh(invoice)
            return invoice
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    @classmethod
    def create_credit_note(cls, db: Session, iid: int, data: dict) -> Invoice:
        inv = db.get(Invoice, iid)
        if not inv:
            raise HTTPException(status_code=404, detail="Fattura d'origine non trovata")
        if inv.tipo_documento == 'TD04':
            raise HTTPException(status_code=400, detail="Impossibile emettere una nota di credito a storno di un'altra nota di credito")

        items_to_reverse = data.get('items', [])
        if not items_to_reverse:
            raise HTTPException(status_code=400, detail="Almeno una riga da stornare richiesta")

        today = date.today()
        anno = today.year
        numero = cls.get_next_credit_note_number(db, anno)
        numero_completo = f"NC-{anno}-{numero:04d}"

        causale = data.get('causale_storno') or f"Storno parziale su fattura {inv.numero_completo}"
        compensa_scadenzario = data.get('compensa_scadenzario', True)
        reintegro_magazzino = data.get('reintegro_magazzino', False)

        items_map = {it.id: it for it in inv.items}
        nc_items = []
        castelletto = {}
        totale_imponibile = 0.0
        totale_imposta = 0.0

        for it_rev in items_to_reverse:
            orig_item_id = it_rev.get('invoice_item_id')
            orig_item = items_map.get(orig_item_id)
            if not orig_item:
                raise HTTPException(status_code=400, detail=f"Riga fattura {orig_item_id} non trovata")

            qta_storno = float(it_rev.get('quantita_stornata', orig_item.quantita))
            if qta_storno <= 0 or qta_storno > orig_item.quantita:
                raise HTTPException(status_code=400, detail=f"Quantità da stornare non valida ({qta_storno})")

            prezzo_unit = float(orig_item.prezzo_unitario)
            aliq = int(orig_item.aliquota_iva or 0)
            imp_riga = round(qta_storno * prezzo_unit, 2)
            imposta_riga = round(imp_riga * (aliq / 100.0), 2)

            totale_imponibile += imp_riga
            totale_imposta += imposta_riga

            aliq_key = str(aliq)
            if aliq_key not in castelletto:
                castelletto[aliq_key] = {"imponibile": 0.0, "imposta": 0.0}
            castelletto[aliq_key]["imponibile"] += imp_riga
            castelletto[aliq_key]["imposta"] += imposta_riga

            nc_items.append(InvoiceItem(
                product_id=orig_item.product_id,
                delivery_note_id=orig_item.delivery_note_id,
                descrizione=f"Storno: {orig_item.descrizione}",
                unita_misura=orig_item.unita_misura,
                colli=int(orig_item.colli or 1),
                quantita=qta_storno,
                prezzo_unitario=prezzo_unit,
                aliquota_iva=aliq,
                imponibile_riga=imp_riga,
                lotto=orig_item.lotto,
                data_scadenza=orig_item.data_scadenza
            ))

            if reintegro_magazzino and orig_item.lotto:
                p_reso = PurchaseDeliveryNote(
                    numero_documento_fornitore=f"RESO-{numero_completo}",
                    fornitore_id=inv.cliente_id,
                    data_ricezione=today,
                    note=f"Reso merci da cliente con Nota di Credito {numero_completo} (storno {inv.numero_completo})",
                    items=[PurchaseDeliveryNoteItem(
                        product_id=orig_item.product_id,
                        descrizione=f"Reso: {orig_item.descrizione}",
                        colli=1,
                        quantita=qta_storno,
                        prezzo_unitario=prezzo_unit,
                        aliquota_iva=aliq,
                        lotto=orig_item.lotto,
                        data_scadenza=orig_item.data_scadenza or today
                    )]
                )
                db.add(p_reso)

        totale_imponibile = round(totale_imponibile, 2)
        totale_imposta = round(totale_imposta, 2)
        totale_nc = round(totale_imponibile + totale_imposta, 2)

        for k in castelletto:
            castelletto[k]["imponibile"] = round(castelletto[k]["imponibile"], 2)
            castelletto[k]["imposta"] = round(castelletto[k]["imposta"], 2)

        nc = Invoice(
            numero=numero,
            anno=anno,
            numero_completo=numero_completo,
            tipo_documento='TD04',
            data_documento=today,
            cliente_id=inv.cliente_id,
            condizioni_pagamento=inv.condizioni_pagamento,
            esigibilita_iva=inv.esigibilita_iva,
            totale_imponibile=totale_imponibile,
            totale_imposta=totale_imposta,
            totale_fattura=totale_nc,
            castelletto_iva=castelletto,
            stato='emessa',
            note=causale,
            invoice_origine_id=inv.id,
            invoice_origine_numero=inv.numero_completo,
            causale_storno=causale,
            reintegro_magazzino=reintegro_magazzino,
            items=nc_items
        )
        db.add(nc)

        if compensa_scadenzario and inv.installments:
            residuo_storno = totale_nc
            sorted_installments = sorted(inv.installments, key=lambda x: x.data_scadenza)
            for inst in sorted_installments:
                if inst.stato == 'aperta' and residuo_storno > 0:
                    if inst.importo <= residuo_storno:
                        residuo_storno = round(residuo_storno - inst.importo, 2)
                        inst.importo = 0.0
                        inst.stato = 'incassata'
                    else:
                        inst.importo = round(inst.importo - residuo_storno, 2)
                        residuo_storno = 0.0

            if all(inst.stato == 'incassata' or inst.importo <= 0.0 for inst in inv.installments):
                inv.stato = 'saldata'

        db.flush()
        je_nc = AccountingService.auto_post_credit_note_to_accounting(db, nc, inv)

        try:
            dispatch_event(
                event_type_code="EMISSIONE_FATTURA",
                azione="emissione_nota_credito",
                titolo=f"Nota di Credito {nc.numero_completo}",
                descrizione=f"Emessa nota di credito {nc.numero_completo} a storno di {inv.numero_completo} ({nc.totale_fattura:.2f} €)",
                entita_tipo="invoice",
                entita_id=nc.id,
                partner_id=nc.cliente_id,
                payload_dati={"totale": float(nc.totale_fattura), "journal_entry_id": je_nc.id if je_nc else None},
                db=db
            )
        except Exception:
            pass

        try:
            db.commit()
            db.refresh(nc)
            return nc
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    @classmethod
    def pay_installment(cls, db: Session, inst_id: int) -> InvoiceInstallment:
        inst = db.get(InvoiceInstallment, inst_id)
        if not inst:
            raise HTTPException(status_code=404, detail="Installment not found")

        inst.stato = 'incassata'
        inst.data_incasso = date.today()

        invoice = inst.invoice
        if all(i.stato == 'incassata' for i in invoice.installments):
            invoice.stato = 'saldata'

        db.flush()
        je_inc = AccountingService.auto_post_installment_payment_to_accounting(db, inst, invoice)

        try:
            dispatch_event(
                event_type_code="INCASSO_RATA",
                azione="incasso_rata",
                titolo=f"Incasso Rata FT {invoice.numero_completo}",
                descrizione=f"Incassata rata {inst.numero_rata}/{inst.totale_rate} per {invoice.numero_completo} ({inst.importo:.2f} €)",
                channel_code="AUDIT",
                category_code="AMMINISTRAZIONE",
                entita_tipo="installment",
                entita_id=inst.id,
                partner_id=invoice.cliente_id,
                payload_dati={"importo": float(inst.importo), "journal_entry_id": je_inc.id if je_inc else None},
                db=db
            )
        except Exception:
            pass

        try:
            db.commit()
            db.refresh(inst)
            return inst
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))
