from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
import calendar
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from models import Invoice, InvoiceItem, InvoiceInstallment, DeliveryNote, Partner, Product
from services.event_dispatcher import dispatch_event
from services.accounting_service import AccountingService
from services.sdi_service import generate_sdi_xml

class InvoiceService:
    @staticmethod
    def get_next_invoice_number(db: Session, anno: int) -> int:
        max_num = db.query(func.max(Invoice.numero)).filter_by(anno=anno).scalar()
        return (max_num or 0) + 1

    @staticmethod
    def get_next_credit_note_number(db: Session, anno: int) -> int:
        max_num = db.query(func.max(Invoice.numero)).filter(Invoice.anno == anno, Invoice.tipo_documento == 'TD04').scalar()
        return (max_num or 0) + 1

    @staticmethod
    def calculate_installments(totale_fattura: float, data_documento: date, condizioni: Optional[str]) -> list:
        if not condizioni or 'gg' not in condizioni:
            return [{"numero_rata": 1, "data_scadenza": data_documento, "importo": totale_fattura}]

        fm = 'fm' in condizioni.lower()
        parts = [p.strip() for p in condizioni.split(' ') if 'gg' in p]
        if not parts:
            return [{"numero_rata": 1, "data_scadenza": data_documento, "importo": totale_fattura}]
            
        giorni_str = parts[0].replace('gg', '')
        try:
            if ',' in giorni_str:
                scadenze_giorni = [int(g) for g in giorni_str.split(',')]
            else:
                scadenze_giorni = [int(giorni_str)]
        except ValueError:
            return [{"numero_rata": 1, "data_scadenza": data_documento, "importo": totale_fattura}]

        rate = []
        num_rate = len(scadenze_giorni)
        base_importo = round(totale_fattura / num_rate, 2)
        differenza = round(totale_fattura - (base_importo * num_rate), 2)

        for i, gg in enumerate(scadenze_giorni):
            data_scad = data_documento + timedelta(days=gg)
            if fm:
                _, last_day = calendar.monthrange(data_scad.year, data_scad.month)
                data_scad = data_scad.replace(day=last_day)
            
            importo_rata = base_importo
            if i == 0:
                importo_rata += differenza

            rate.append({
                "numero_rata": i + 1,
                "data_scadenza": data_scad,
                "importo": importo_rata
            })
        return rate

    @classmethod
    def create_invoice_from_ddt(cls, db: Session, ddt_id: int) -> Invoice:
        ddt = db.get(DeliveryNote, ddt_id)
        if not ddt:
            raise HTTPException(status_code=404, detail="DDT not found")
        if getattr(ddt, 'invoice_id', None):
            raise HTTPException(status_code=400, detail="DDT già fatturato")
        if ddt.stato != 'confermato':
            raise HTTPException(status_code=400, detail="Il DDT non è confermato")
        if not ddt.cliente:
            raise HTTPException(status_code=400, detail="DDT senza cliente")

        today = date.today()
        anno = today.year
        numero = cls.get_next_invoice_number(db, anno)
        numero_completo = f"FTE-{anno}-{numero:04d}"

        invoice_items = []
        totale_imponibile = 0.0
        totale_imposta = 0.0
        castelletto_iva = {}

        for d_item in ddt.items:
            qta = float(d_item.quantita or 0.0)
            prezzo = float(d_item.prezzo_unitario or 0.0)
            imponibile_riga = round(qta * prezzo, 2)
            aliquota = int(d_item.aliquota_iva or 22)
            imposta_riga = round(imponibile_riga * (aliquota / 100), 2)

            totale_imponibile += imponibile_riga
            totale_imposta += imposta_riga

            if str(aliquota) not in castelletto_iva:
                castelletto_iva[str(aliquota)] = {"imponibile": 0.0, "imposta": 0.0}
            castelletto_iva[str(aliquota)]["imponibile"] += imponibile_riga
            castelletto_iva[str(aliquota)]["imposta"] += imposta_riga

            invoice_items.append(InvoiceItem(
                delivery_note_id=ddt.id,
                product_id=d_item.product_id,
                descrizione=d_item.descrizione,
                unita_misura=d_item.unita_misura,
                colli=d_item.colli,
                quantita=qta,
                prezzo_unitario=prezzo,
                aliquota_iva=aliquota,
                imponibile_riga=imponibile_riga,
                lotto=d_item.lotto,
                data_scadenza=d_item.data_scadenza
            ))

        for k in castelletto_iva:
            castelletto_iva[k]["imponibile"] = round(castelletto_iva[k]["imponibile"], 2)
            castelletto_iva[k]["imposta"] = round(castelletto_iva[k]["imposta"], 2)

        totale_fattura = round(totale_imponibile + totale_imposta, 2)

        condizioni_pagamento = ddt.cliente.condizioni_pagamento or "30gg fm"
        rate_calc = cls.calculate_installments(totale_fattura, today, condizioni_pagamento)
        
        installments = []
        for rc in rate_calc:
            installments.append(InvoiceInstallment(
                numero_rata=rc["numero_rata"],
                totale_rate=len(rate_calc),
                data_scadenza=rc["data_scadenza"],
                importo=rc["importo"],
                stato='aperta'
            ))

        invoice = Invoice(
            numero=numero,
            anno=anno,
            numero_completo=numero_completo,
            cliente_id=ddt.cliente_id,
            tipo_documento="TD24",
            data_documento=today,
            condizioni_pagamento=condizioni_pagamento,
            esigibilita_iva="I",
            totale_imponibile=round(totale_imponibile, 2),
            totale_imposta=round(totale_imposta, 2),
            totale_fattura=totale_fattura,
            castelletto_iva=castelletto_iva,
            stato='emessa',
            note=f"Fattura differita da {ddt.numero_completo}",
            items=invoice_items,
            installments=installments
        )

        db.add(invoice)
        db.flush()

        ddt.invoice_id = invoice.id
        ddt.stato = 'fatturato'
        db.flush()

        # Prima nota
        je = AccountingService.auto_post_invoice_to_accounting(db, invoice)
        
        try:
            dispatch_event(
                db=db,
                event_type_code="EMISSIONE_FATTURA",
                azione="emissione_fattura",
                titolo=f"Fattura {invoice.numero_completo}",
                descrizione=f"Emessa fattura differita {invoice.numero_completo} - Totale {invoice.totale_fattura:.2f} €",
                channel_code="AUDIT",
                category_code="AMMINISTRAZIONE",
                entita_tipo="invoice",
                entita_id=invoice.id,
                partner_id=invoice.cliente_id,
                payload_dati={"totale": float(invoice.totale_fattura), "journal_entry_id": je.id if je else None}
            )
        except Exception:
            pass

        db.commit()
        db.refresh(invoice)
        return invoice

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
        today = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()
        anno = today.year
        numero = cls.get_next_invoice_number(db, anno)
        numero_completo = f"FTE-{anno}-{numero:04d}"

        invoice_items = []
        totale_imponibile = 0.0
        totale_imposta = 0.0
        castelletto_iva = {}

        for idx, it in enumerate(items_data):
            qta = float(it.get('quantita', 1.0))
            prezzo = float(it.get('prezzo_unitario', 0.0))
            aliquota = int(it.get('aliquota_iva', 22))
            imponibile_riga = round(qta * prezzo, 2)
            imposta_riga = round(imponibile_riga * (aliquota / 100), 2)

            totale_imponibile += imponibile_riga
            totale_imposta += imposta_riga

            if str(aliquota) not in castelletto_iva:
                castelletto_iva[str(aliquota)] = {"imponibile": 0.0, "imposta": 0.0}
            castelletto_iva[str(aliquota)]["imponibile"] += imponibile_riga
            castelletto_iva[str(aliquota)]["imposta"] += imposta_riga

            invoice_items.append(InvoiceItem(
                product_id=it.get('product_id'),
                descrizione=it.get('descrizione', 'Articolo Varie'),
                unita_misura=it.get('unita_misura', 'PZ'),
                colli=int(it.get('colli', 1)),
                quantita=qta,
                prezzo_unitario=prezzo,
                aliquota_iva=aliquota,
                imponibile_riga=imponibile_riga
            ))

        for k in castelletto_iva:
            castelletto_iva[k]["imponibile"] = round(castelletto_iva[k]["imponibile"], 2)
            castelletto_iva[k]["imposta"] = round(castelletto_iva[k]["imposta"], 2)

        totale_fattura = round(totale_imponibile + totale_imposta, 2)

        condizioni_pagamento = data.get('condizioni_pagamento') or cliente.condizioni_pagamento or "30gg fm"
        rate_calc = cls.calculate_installments(totale_fattura, today, condizioni_pagamento)

        installments = []
        for rc in rate_calc:
            installments.append(InvoiceInstallment(
                numero_rata=rc["numero_rata"],
                totale_rate=len(rate_calc),
                data_scadenza=rc["data_scadenza"],
                importo=rc["importo"],
                stato='aperta'
            ))

        invoice = Invoice(
            numero=numero,
            anno=anno,
            numero_completo=numero_completo,
            cliente_id=cliente.id,
            tipo_documento=data.get('tipo_documento', "TD01"),
            data_documento=today,
            condizioni_pagamento=condizioni_pagamento,
            esigibilita_iva=data.get('esigibilita_iva', "I"),
            totale_imponibile=round(totale_imponibile, 2),
            totale_imposta=round(totale_imposta, 2),
            totale_fattura=totale_fattura,
            castelletto_iva=castelletto_iva,
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
                db=db,
                event_type_code="EMISSIONE_FATTURA",
                azione="emissione_fattura",
                titolo=f"Fattura {invoice.numero_completo}",
                descrizione=f"Emessa fattura {invoice.numero_completo} ({invoice.tipo_documento}) - Totale {invoice.totale_fattura:.2f} €",
                channel_code="AUDIT",
                category_code="AMMINISTRAZIONE",
                entita_tipo="invoice",
                entita_id=invoice.id,
                partner_id=invoice.cliente_id,
                payload_dati={"totale": float(invoice.totale_fattura), "journal_entry_id": je.id if je else None}
            )
        except Exception:
            pass

        db.commit()
        db.refresh(invoice)
        return invoice

    @classmethod
    def create_credit_note(cls, db: Session, iid: int, data: dict) -> Invoice:
        inv = db.get(Invoice, iid)
        if not inv:
            raise HTTPException(status_code=404, detail="Fattura d'origine non trovata")
        if inv.tipo_documento == 'TD04':
            raise HTTPException(status_code=400, detail="Impossibile creare una nota di credito da un'altra nota di credito")

        importo_storno_richiesto = data.get('importo_storno')
        if not importo_storno_richiesto:
            raise HTTPException(status_code=400, detail="Specificare importo_storno")
        
        importo_storno = float(importo_storno_richiesto)
        if importo_storno <= 0 or importo_storno > inv.totale_fattura:
            raise HTTPException(status_code=400, detail="Importo storno non valido o superiore al totale fattura")

        ratio = importo_storno / float(inv.totale_fattura)
        totale_imponibile_nc = round(float(inv.totale_imponibile) * ratio, 2)
        totale_imposta_nc = round(float(inv.totale_imposta) * ratio, 2)
        reintegro_magazzino = data.get('reintegro_magazzino', False)

        today = date.today()
        anno = today.year
        numero_nc = cls.get_next_credit_note_number(db, anno)
        numero_completo_nc = f"NC-{anno}-{numero_nc:04d}"

        castelletto_nc = {}
        for k, v in (inv.castelletto_iva or {}).items():
            castelletto_nc[k] = {
                "imponibile": round(float(v["imponibile"]) * ratio, 2),
                "imposta": round(float(v["imposta"]) * ratio, 2)
            }

        nc_items = []
        for org_item in inv.items:
            nc_items.append(InvoiceItem(
                product_id=org_item.product_id,
                descrizione=f"Storno: {org_item.descrizione}",
                unita_misura=org_item.unita_misura,
                colli=org_item.colli,
                quantita=org_item.quantita * ratio,
                prezzo_unitario=org_item.prezzo_unitario,
                aliquota_iva=org_item.aliquota_iva,
                imponibile_riga=round(org_item.imponibile_riga * ratio, 2),
                lotto=org_item.lotto
            ))

        nc = Invoice(
            numero=numero_nc,
            anno=anno,
            numero_completo=numero_completo_nc,
            cliente_id=inv.cliente_id,
            tipo_documento="TD04",
            data_documento=today,
            condizioni_pagamento="Storno a pareggio",
            esigibilita_iva="I",
            totale_imponibile=totale_imponibile_nc,
            totale_imposta=totale_imposta_nc,
            totale_fattura=importo_storno,
            castelletto_iva=castelletto_nc,
            stato='emessa',
            invoice_origine_id=inv.id,
            invoice_origine_numero=inv.numero_completo,
            causale_storno=data.get('causale_storno', 'Reso o abbuono'),
            reintegro_magazzino=reintegro_magazzino,
            items=nc_items
        )
        db.add(nc)
        db.flush()

        if abs(importo_storno - float(inv.totale_fattura)) < 0.01:
            inv.stato = 'stornata'
            for inst in inv.installments:
                if inst.stato == 'aperta':
                    inst.stato = 'annullata'
        else:
            residuo_da_compensare = importo_storno
            for inst in reversed(inv.installments):
                if inst.stato == 'aperta' and residuo_da_compensare > 0:
                    if float(inst.importo) <= residuo_da_compensare:
                        residuo_da_compensare -= float(inst.importo)
                        inst.stato = 'annullata'
                    else:
                        inst.importo = round(float(inst.importo) - residuo_da_compensare, 2)
                        residuo_da_compensare = 0

            if all(i.stato in ['incassata', 'annullata'] for i in inv.installments):
                inv.stato = 'saldata'

        try:
            dispatch_event(
                db=db,
                event_type_code="NOTA_CREDITO",
                azione="nota_credito",
                titolo=f"Nota di Credito {nc.numero_completo}",
                descrizione=f"Emessa nota di credito a fronte di {inv.numero_completo}",
                channel_code="AUDIT",
                category_code="AMMINISTRAZIONE",
                entita_tipo="invoice",
                entita_id=nc.id,
                partner_id=nc.cliente_id
            )
        except Exception:
            pass

        db.commit()
        db.refresh(nc)
        return nc

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
        
        # Scrittura contabile automatica Incasso
        from seed_accounting import seed_default_accounting_causals
        from models import AccountingCausal, JournalEntry, JournalItem
        seed_default_accounting_causals(db)
        causal_inc = db.query(AccountingCausal).filter_by(codice="INCASSO_RATA", attivo=True).first()
        je_inc = None
        
        if causal_inc and causal_inc.conto_dare_id and causal_inc.conto_avere_id:
            anno_c = date.today().year
            num_c = AccountingService.get_next_journal_entry_number(db, anno_c)
            num_comp_c = f"PN-{anno_c}-{num_c:04d}"
            importo_inc = float(inst.importo)
            cli_nome = invoice.cliente.ragione_sociale if invoice.cliente else "Cliente"

            je_inc = JournalEntry(
                numero=num_c,
                anno=anno_c,
                numero_completo=num_comp_c,
                data_registrazione=date.today(),
                data_competenza=date.today(),
                causale=f"Incasso rata {inst.numero_rata}/{inst.totale_rate} fattura {invoice.numero_completo} da {cli_nome}",
                causale_id=causal_inc.id,
                totale_dare=importo_inc,
                totale_avere=importo_inc,
                stato="confermata"
            )
            db.add(je_inc)
            db.flush()

            db.add(JournalItem(
                journal_entry_id=je_inc.id,
                account_id=causal_inc.conto_dare_id,
                descrizione_riga=f"Incasso banca rata {inst.numero_rata} FT {invoice.numero_completo}",
                dare=importo_inc,
                avere=0.0
            ))
            db.add(JournalItem(
                journal_entry_id=je_inc.id,
                account_id=causal_inc.conto_avere_id,
                partner_id=invoice.cliente_id,
                descrizione_riga=f"Chiusura credito rata {inst.numero_rata} FT {invoice.numero_completo}",
                dare=0.0,
                avere=importo_inc
            ))

        try:
            dispatch_event(
                db=db,
                event_type_code="INCASSO_RATA",
                azione="incasso_rata",
                titolo=f"Incasso Rata FT {invoice.numero_completo}",
                descrizione=f"Incassata rata {inst.numero_rata}/{inst.totale_rate} per {invoice.numero_completo} ({inst.importo:.2f} €)",
                channel_code="AUDIT",
                category_code="AMMINISTRAZIONE",
                entita_tipo="installment",
                entita_id=inst.id,
                partner_id=invoice.cliente_id,
                payload_dati={"importo": float(inst.importo), "journal_entry_id": je_inc.id if je_inc else None}
            )
        except Exception:
            pass

        db.commit()
        db.refresh(inst)
        return inst
