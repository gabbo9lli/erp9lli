import os
import shutil
import subprocess
import csv
import io
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import (
    Partner, Product, PurchaseDeliveryNote, PurchaseDeliveryNoteItem,
    Invoice, InvoiceItem, InvoiceInstallment, LegacyMigrationSync,
    Account, AccountingCausal
)
from seed_accounting import seed_chart_of_accounts, seed_default_accounting_causals
from services.event_dispatcher import dispatch_event

class LegacyMigrationService:
    @staticmethod
    def _find_mdb_tool(tool_name: str) -> str:
        found = shutil.which(tool_name)
        if found:
            return found
        homebrew_path = f"/opt/homebrew/bin/{tool_name}"
        if os.path.exists(homebrew_path):
            return homebrew_path
        usr_path = f"/usr/bin/{tool_name}"
        if os.path.exists(usr_path):
            return usr_path
        return tool_name

    @classmethod
    def _resolve_file_path(cls, source_file: str) -> str:
        if os.path.exists(source_file):
            return source_file
        filename = os.path.basename(source_file)
        candidates = [
            os.path.join("/app/data/uploads", filename),
            os.path.join("/app/data", filename),
            os.path.join(os.getcwd(), "data", "uploads", filename),
            os.path.join(os.getcwd(), "data", filename),
            os.path.join(os.getcwd(), "backend", "data", filename),
            os.path.join("/opt/erp9lli/data/uploads", filename),
            os.path.join("/opt/erp9lli/data", filename),
            os.path.join("/tmp/legacy_uploads", filename),
            os.path.join("/tmp", filename),
            filename
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return source_file

    @classmethod
    def _export_table_rows(cls, source_file: str, table_name: str, delimiter: str = '|') -> List[Dict[str, str]]:
        source_file = cls._resolve_file_path(source_file)
        if not os.path.exists(source_file):
            raise FileNotFoundError(f"Database file not found: {source_file}")

        tool = cls._find_mdb_tool('mdb-export')
        cmd = [tool, '-R', '\n', '-d', delimiter, source_file, table_name]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            output = res.stdout
            if not output.strip():
                return []
            reader = csv.DictReader(io.StringIO(output), delimiter=delimiter)
            return list(reader)
        except Exception as e:
            return []

    @classmethod
    def parse_access_date(cls, val: Optional[str]) -> Optional[date]:
        if not val:
            return None
        val = val.strip().replace('"', '')
        if not val:
            return None
        date_part = val.split(' ')[0]
        # In Access, dates are commonly MM/DD/YY or DD/MM/YY
        for fmt in ('%m/%d/%y', '%d/%m/%y', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d'):
            try:
                parsed = datetime.strptime(date_part, fmt).date()
                if parsed.year < 1980:
                    parsed = parsed.replace(year=parsed.year + 100)
                return parsed
            except ValueError:
                pass
        return None

    @classmethod
    def inspect_database(cls, source_file: str) -> Dict[str, Any]:
        source_file = cls._resolve_file_path(source_file)
        if not os.path.exists(source_file):
            return {"is_valid": False, "error": f"File non trovato: {source_file}", "source_file": source_file, "tables": []}

        tool = cls._find_mdb_tool('mdb-tables')
        try:
            res = subprocess.run([tool, '-1', source_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            tables = [t.strip() for t in res.stdout.splitlines() if t.strip()]
            return {
                "is_valid": len(tables) > 0,
                "source_file": source_file,
                "file_size_mb": round(os.path.getsize(source_file) / (1024 * 1024), 2),
                "tables_count": len(tables),
                "tables": tables
            }
        except Exception as e:
            return {"is_valid": False, "error": str(e), "source_file": source_file, "tables": []}

    @classmethod
    def dry_run(cls, source_file: str) -> Dict[str, Any]:
        info = cls.inspect_database(source_file)
        if not info.get("is_valid"):
            return {
                "status": "error",
                "error": info.get("error", "Database non valido"),
                "source_file": source_file,
                "partners_count": 0,
                "products_count": 0,
                "stock_lots_count": 0,
                "invoices_count": 0,
                "installments_count": 0,
                "estimated_seconds": 0
            }

        tables = info.get("tables", [])

        partners_count = 0
        products_count = 0
        stock_lots_count = 0
        invoices_count = 0
        installments_count = 0

        # Partners & Invoices estimate
        if "T_AllaDataFA" in tables:
            rows = cls._export_table_rows(source_file, "T_AllaDataFA")
            client_ids = {r.get("IdCliente") for r in rows if r.get("IdCliente")}
            producers = {r.get("produttore") for r in rows if r.get("produttore")}
            partners_count = len(client_ids) + len(producers)
            inv_ids = {r.get("IdFF") for r in rows if r.get("IdFF")}
            invoices_count = len(inv_ids)

        # Products estimate
        if "Tabella1CReg" in tables:
            rows_prod = cls._export_table_rows(source_file, "Tabella1CReg")
            art_ids = {r.get("IdArt") for r in rows_prod if r.get("IdArt")}
            products_count = len(art_ids)
        elif "T_AllaDataFA" in tables:
            art_ids = {r.get("idArt") for r in rows if r.get("idArt")}
            products_count = len(art_ids)

        # Stock lots estimate
        if "T2" in tables:
            rows_t2 = cls._export_table_rows(source_file, "T2")
            stock_lots_count = len([r for r in rows_t2 if float(r.get("totgiac") or 0.0) > 0])

        # Installments estimate
        if "ScadenzarioPRT" in tables:
            rows_scad = cls._export_table_rows(source_file, "ScadenzarioPRT")
            installments_count = len(rows_scad)

        return {
            "status": "success",
            "source_file": source_file,
            "partners_count": max(partners_count, 1),
            "products_count": max(products_count, 1),
            "stock_lots_count": stock_lots_count,
            "invoices_count": invoices_count,
            "installments_count": installments_count,
            "estimated_seconds": max(5, int((partners_count + products_count + invoices_count) / 500))
        }

    @classmethod
    def extract_and_migrate_partners(cls, db: Session, source_file: str, limit: Optional[int] = None) -> int:
        filename = os.path.basename(source_file)
        rows = cls._export_table_rows(source_file, "T_AllaDataFA")
        if not rows:
            rows = cls._export_table_rows(source_file, "FattureElMese")

        seen_clients = {}
        producers = set()

        for r in rows:
            cid = r.get("IdCliente") or r.get("idcliente")
            ragsoc = (r.get("RagSoc") or r.get("ragsoc") or "").strip().replace('"', '')
            if cid and ragsoc and cid not in seen_clients:
                seen_clients[cid] = ragsoc

            prod = (r.get("produttore") or "").strip().replace('"', '')
            if prod:
                producers.add(prod)

        migrated = 0
        items_to_process = list(seen_clients.items())
        if limit:
            items_to_process = items_to_process[:limit]

        for legacy_id, ragsoc in items_to_process:
            sync = db.query(LegacyMigrationSync).filter_by(
                source_file=filename, entity_type="partner", legacy_id=str(legacy_id)
            ).first()
            if sync:
                continue

            partner = db.query(Partner).filter_by(ragione_sociale=ragsoc).first()
            if not partner:
                partner = Partner(
                    ragione_sociale=ragsoc,
                    tipo="cliente",
                    nazione="IT",
                    attivo=True
                )
                db.add(partner)
                db.flush()
                migrated += 1

            db.add(LegacyMigrationSync(
                source_file=filename,
                entity_type="partner",
                legacy_id=str(legacy_id),
                target_id=partner.id
            ))

        for prod_nome in list(producers)[: (limit or len(producers))]:
            sync = db.query(LegacyMigrationSync).filter_by(
                source_file=filename, entity_type="partner", legacy_id=f"PROD-{prod_nome}"
            ).first()
            if sync:
                continue

            partner = db.query(Partner).filter_by(ragione_sociale=prod_nome).first()
            if not partner:
                partner = Partner(
                    ragione_sociale=prod_nome,
                    tipo="fornitore",
                    nazione="IT",
                    attivo=True
                )
                db.add(partner)
                db.flush()
                migrated += 1

            db.add(LegacyMigrationSync(
                source_file=filename,
                entity_type="partner",
                legacy_id=f"PROD-{prod_nome}",
                target_id=partner.id
            ))

        db.commit()
        return migrated

    @classmethod
    def extract_and_migrate_products(cls, db: Session, source_file: str, limit: Optional[int] = None) -> int:
        filename = os.path.basename(source_file)
        rows = cls._export_table_rows(source_file, "Tabella1CReg")
        if not rows:
            rows = cls._export_table_rows(source_file, "T_AllaDataFA")

        seen_articles = {}
        for r in rows:
            aid = r.get("IdArt") or r.get("idArt") or r.get("idart")
            cod = (r.get("CodArt") or r.get("codArt") or "").strip().replace('"', '')
            desc = (r.get("DescArt") or r.get("descArt") or "").strip().replace('"', '')
            if aid and desc and aid not in seen_articles:
                seen_articles[aid] = {
                    "codice": cod or f"ART-{aid}",
                    "descrizione": desc,
                    "um": (r.get("um") or "KG").strip().replace('"', ''),
                    "prezzo_vendita": float(r.get("prezzoArt") or r.get("Prezzo") or 0.0),
                    "prezzo_acquisto": float(r.get("PrezzoMovAcq") or 0.0),
                    "codice_nc": (r.get("CodiceNC") or "").strip().replace('"', '')
                }

        items_to_process = list(seen_articles.items())
        if limit:
            items_to_process = items_to_process[:limit]

        migrated = 0
        for legacy_id, art_data in items_to_process:
            sync = db.query(LegacyMigrationSync).filter_by(
                source_file=filename, entity_type="product", legacy_id=str(legacy_id)
            ).first()
            if sync:
                continue

            codice = art_data["codice"]
            prod = db.query(Product).filter_by(codice=codice).first()
            if not prod:
                pv = round(art_data["prezzo_vendita"], 2)
                pa = round(art_data["prezzo_acquisto"] or (pv * 0.70), 2)
                um_norm = "PZ" if art_data["um"] == "N." else (art_data["um"] or "KG")
                cat = "imballo" if "imball" in art_data["descrizione"].lower() or "cassa" in art_data["descrizione"].lower() else "fresco"

                prod = Product(
                    codice=codice,
                    descrizione=art_data["descrizione"],
                    categoria=cat,
                    unita_misura=um_norm,
                    peso_netto=1.0,
                    prezzo_vendita=pv,
                    prezzo_acquisto=pa,
                    aliquota_iva=4,
                    in_scadenza=True,
                    attivo=True,
                    codice_nc=art_data["codice_nc"] or None
                )
                db.add(prod)
                db.flush()
                migrated += 1

            db.add(LegacyMigrationSync(
                source_file=filename,
                entity_type="product",
                legacy_id=str(legacy_id),
                target_id=prod.id
            ))

        db.commit()
        return migrated

    @classmethod
    def extract_and_migrate_stock_lots(cls, db: Session, source_file: str, limit: Optional[int] = None) -> int:
        filename = os.path.basename(source_file)
        rows = cls._export_table_rows(source_file, "T2")
        if not rows:
            return 0

        supplier = db.query(Partner).filter_by(tipo="fornitore").first()
        if not supplier:
            supplier = Partner(ragione_sociale="Fornitore Inventario Iniziale", tipo="fornitore", nazione="IT")
            db.add(supplier)
            db.flush()

        doc_num = f"INV-LEGACY-{datetime.utcnow().year}"
        pnote = db.query(PurchaseDeliveryNote).filter_by(numero_documento_fornitore=doc_num).first()
        if not pnote:
            pnote = PurchaseDeliveryNote(
                numero_documento_fornitore=doc_num,
                data_documento=date.today(),
                data_ricezione=date.today(),
                fornitore_id=supplier.id,
                note="Inventario lotti iniziali da migrazione legacy Access (T2)"
            )
            db.add(pnote)
            db.flush()

        migrated = 0
        items_to_process = rows[:limit] if limit else rows

        aggregated_t2 = {}
        for r in items_to_process:
            qta = float(r.get("totgiac") or 0.0)
            if qta <= 0:
                continue
            aid = str(r.get("IdArt"))
            lotto = (r.get("lotto") or "L-LEGACY").strip().replace('"', '')
            scad_raw = (r.get("ScadenzaR") or "").strip().replace('"', '')
            key = (aid, lotto, scad_raw)
            aggregated_t2[key] = aggregated_t2.get(key, 0.0) + qta

        for (aid, lotto, scad_raw), qta in aggregated_t2.items():
            scadenza = cls.parse_access_date(scad_raw)
            sync_key = f"{aid}_{lotto}_{scad_raw}"

            sync_prod = db.query(LegacyMigrationSync).filter_by(
                source_file=filename, entity_type="product", legacy_id=aid
            ).first()
            p_id = sync_prod.target_id if sync_prod else None
            prod = db.get(Product, p_id) if p_id else None
            if not prod:
                prod = db.query(Product).first()
            if not prod:
                continue

            sync_lot = db.query(LegacyMigrationSync).filter_by(
                source_file=filename, entity_type="stock_lot", legacy_id=sync_key
            ).first()
            if sync_lot:
                continue

            pnote_item = PurchaseDeliveryNoteItem(
                purchase_delivery_note_id=pnote.id,
                product_id=prod.id,
                descrizione=prod.descrizione,
                unita_misura=prod.unita_misura,
                colli=int(qta),
                quantita=qta,
                prezzo_unitario=prod.prezzo_acquisto or 1.0,
                aliquota_iva=prod.aliquota_iva or 4,
                lotto=lotto,
                data_scadenza=scadenza or date.today()
            )
            db.add(pnote_item)
            db.flush()
            migrated += 1

            db.add(LegacyMigrationSync(
                source_file=filename,
                entity_type="stock_lot",
                legacy_id=sync_key,
                target_id=pnote_item.id
            ))

        db.commit()
        return migrated

    @classmethod
    def extract_and_migrate_invoices_and_installments(
        cls, db: Session, source_file: str, limit: Optional[int] = None
    ) -> Tuple[int, int]:
        filename = os.path.basename(source_file)
        rows_inv = cls._export_table_rows(source_file, "T_AllaDataFA")
        if not rows_inv:
            return 0, 0

        # Group rows by IdFF
        invoices_map: Dict[str, List[Dict[str, str]]] = {}
        for r in rows_inv:
            idff = r.get("IdFF")
            if idff:
                invoices_map.setdefault(idff, []).append(r)

        # Map installments from ScadenzarioPRT
        rows_scad = cls._export_table_rows(source_file, "ScadenzarioPRT")
        scad_by_idff: Dict[str, List[Dict[str, str]]] = {}
        for s in rows_scad:
            idff = s.get("idff")
            if idff:
                scad_by_idff.setdefault(idff, []).append(s)

        migrated_invoices = 0
        migrated_installments = 0

        idff_list = list(invoices_map.keys())
        if limit:
            idff_list = idff_list[:limit]

        for idff in idff_list:
            sync_inv = db.query(LegacyMigrationSync).filter_by(
                source_file=filename, entity_type="invoice", legacy_id=str(idff)
            ).first()
            if sync_inv:
                continue

            inv_rows = invoices_map[idff]
            first_row = inv_rows[0]

            cid = str(first_row.get("IdCliente"))
            sync_cli = db.query(LegacyMigrationSync).filter_by(
                source_file=filename, entity_type="partner", legacy_id=cid
            ).first()
            cli_id = sync_cli.target_id if sync_cli else None
            if not cli_id:
                fallback_cli = db.query(Partner).filter_by(tipo="cliente").first() or db.query(Partner).first()
                cli_id = fallback_cli.id if fallback_cli else None
            if not cli_id:
                continue

            doc_date = cls.parse_access_date(first_row.get("datafatt")) or date.today()
            anno = doc_date.year
            try:
                num = int(first_row.get("NFatt") or idff)
            except ValueError:
                num = int(idff)
            numero_completo = f"FT-{anno}-{num:04d}"

            totale_imponibile = 0.0
            totale_imposta = 0.0
            castelletto = {}
            items = []

            for r_it in inv_rows:
                aid = str(r_it.get("idArt"))
                sync_art = db.query(LegacyMigrationSync).filter_by(
                    source_file=filename, entity_type="product", legacy_id=aid
                ).first()
                p_id = sync_art.target_id if sync_art else None
                prod = db.get(Product, p_id) if p_id else None
                if not prod:
                    prod = db.query(Product).first()
                p_id = prod.id if prod else None
                if not p_id:
                    continue

                qta = float(r_it.get("xqta") or r_it.get("usciti") or 1.0)
                prezzo = float(r_it.get("prezzofatt") or r_it.get("prezzoArt") or (prod.prezzo_vendita if prod else 1.0))
                aliq = prod.aliquota_iva if (prod and prod.aliquota_iva is not None) else 4
                imp = round(qta * prezzo, 2)
                iva = round(imp * (aliq / 100.0), 2)

                totale_imponibile += imp
                totale_imposta += iva

                aliq_str = str(aliq)
                if aliq_str not in castelletto:
                    castelletto[aliq_str] = {"imponibile": 0.0, "imposta": 0.0}
                castelletto[aliq_str]["imponibile"] = round(castelletto[aliq_str]["imponibile"] + imp, 2)
                castelletto[aliq_str]["imposta"] = round(castelletto[aliq_str]["imposta"] + iva, 2)

                items.append(InvoiceItem(
                    product_id=p_id,
                    descrizione=r_it.get("DescArt", prod.descrizione if prod else "Articolo"),
                    unita_misura=r_it.get("um", prod.unita_misura if prod else "KG"),
                    colli=1,
                    quantita=qta,
                    prezzo_unitario=prezzo,
                    aliquota_iva=aliq,
                    imponibile_riga=imp
                ))

            totale_fattura = round(totale_imponibile + totale_imposta, 2)

            invoice = Invoice(
                numero=num,
                anno=anno,
                numero_completo=numero_completo,
                tipo_documento="TD01",
                data_documento=doc_date,
                cliente_id=cli_id,
                condizioni_pagamento="30gg fm",
                esigibilita_iva="I",
                totale_imponibile=totale_imponibile,
                totale_imposta=totale_imposta,
                totale_fattura=totale_fattura,
                castelletto_iva=castelletto if castelletto else {"4": {"imponibile": totale_imponibile, "imposta": totale_imposta}},
                stato="emessa",
                note=f"Importata da Access IdFF={idff}",
                items=items
            )
            db.add(invoice)
            db.flush()
            migrated_invoices += 1

            # Scadenze rate
            scad_rows = scad_by_idff.get(idff, [])
            if scad_rows:
                for idx, s in enumerate(scad_rows):
                    imp_scad = float(s.get("importoscadenza") or (totale_fattura / len(scad_rows)))
                    dt_scad = cls.parse_access_date(s.get("scadenza")) or doc_date
                    pagato = str(s.get("pagato", "0")) in ("1", "True", "true")
                    st = "incassata" if pagato else "aperta"

                    inst = InvoiceInstallment(
                        invoice_id=invoice.id,
                        numero_rata=idx + 1,
                        totale_rate=len(scad_rows),
                        data_scadenza=dt_scad,
                        importo=round(imp_scad, 2),
                        stato=st,
                        data_incasso=cls.parse_access_date(s.get("datapagamento")) if pagato else None
                    )
                    db.add(inst)
                    migrated_installments += 1
            else:
                inst = InvoiceInstallment(
                    invoice_id=invoice.id,
                    numero_rata=1,
                    totale_rate=1,
                    data_scadenza=doc_date,
                    importo=totale_fattura,
                    stato="aperta"
                )
                db.add(inst)
                migrated_installments += 1

            db.add(LegacyMigrationSync(
                source_file=filename,
                entity_type="invoice",
                legacy_id=str(idff),
                target_id=invoice.id,
                anno=anno
            ))

        db.commit()
        return migrated_invoices, migrated_installments

    @classmethod
    def _notify_event_progress(cls, db: Session, event, progresso: int, descrizione: str):
        if not event:
            return
        try:
            event.progresso = progresso
            event.descrizione = descrizione
            db.commit()
            from api.websocket_manager import manager
            manager.broadcast_sync({
                "type": "SYSTEM_EVENT",
                "action": "progress",
                "event": event.to_dict()
            })
        except Exception:
            pass

    @classmethod
    def run_full_migration(cls, db: Session, source_file: str, options: dict = None, event: Optional[Any] = None) -> Dict[str, Any]:
        options = options or {}
        limit = options.get("limit_per_table")

        cls._notify_event_progress(db, event, 10, f"Avvio scansione database {os.path.basename(source_file)}...")
        
        p_count = cls.extract_and_migrate_partners(db, source_file, limit=limit)
        cls._notify_event_progress(db, event, 25, f"Migrati {p_count} partner e produttori...")

        prod_count = cls.extract_and_migrate_products(db, source_file, limit=limit)
        cls._notify_event_progress(db, event, 50, f"Migrati {prod_count} articoli biologici...")

        stock_count = cls.extract_and_migrate_stock_lots(db, source_file, limit=limit)
        cls._notify_event_progress(db, event, 75, f"Migrati {stock_count} lotti di giacenza magazzino...")

        inv_count, inst_count = cls.extract_and_migrate_invoices_and_installments(db, source_file, limit=limit)
        cls._notify_event_progress(db, event, 95, f"Migrate {inv_count} fatture e {inst_count} rate scadenzario...")

        cls._notify_event_progress(db, event, 100, f"Migrazione completata con successo da {os.path.basename(source_file)}")

        return {
            "status": "success",
            "source_file": source_file,
            "migrated_partners": p_count,
            "migrated_products": prod_count,
            "migrated_stock_lots": stock_count,
            "migrated_invoices": inv_count,
            "migrated_installments": inst_count
        }

    @classmethod
    def reset_database(cls, db: Session, confirm_wipe: str) -> Dict[str, Any]:
        from fastapi import HTTPException
        if confirm_wipe != "RESET_ERP9LLI":
            raise HTTPException(
                status_code=400,
                detail="Token di conferma errato. Per confermare il reset digitare 'RESET_ERP9LLI'"
            )

        from models import (
            JournalItem, JournalEntry,
            InvoiceInstallment, InvoiceItem, Invoice,
            CmrItem, CmrDocument,
            DeliveryNoteItem, DeliveryNote,
            OrderItem, CustomerOrder,
            PurchaseDeliveryNoteItem, PurchaseDeliveryNote,
            PalletReceiptItem, PalletReceipt,
            PosSaleItem, PosSale,
            EcommerceSyncLog, SystemEvent,
            LegacyMigrationSync,
            Product, Partner
        )

        try:
            # Delete transactional tables
            db.query(JournalItem).delete(synchronize_session=False)
            db.query(JournalEntry).delete(synchronize_session=False)
            db.query(InvoiceInstallment).delete(synchronize_session=False)
            db.query(InvoiceItem).delete(synchronize_session=False)
            db.query(Invoice).delete(synchronize_session=False)
            db.query(CmrItem).delete(synchronize_session=False)
            db.query(CmrDocument).delete(synchronize_session=False)
            db.query(DeliveryNoteItem).delete(synchronize_session=False)
            db.query(DeliveryNote).delete(synchronize_session=False)
            db.query(OrderItem).delete(synchronize_session=False)
            db.query(CustomerOrder).delete(synchronize_session=False)
            db.query(PurchaseDeliveryNoteItem).delete(synchronize_session=False)
            db.query(PurchaseDeliveryNote).delete(synchronize_session=False)
            db.query(PalletReceiptItem).delete(synchronize_session=False)
            db.query(PalletReceipt).delete(synchronize_session=False)
            db.query(PosSaleItem).delete(synchronize_session=False)
            db.query(PosSale).delete(synchronize_session=False)
            db.query(EcommerceSyncLog).delete(synchronize_session=False)
            db.query(SystemEvent).delete(synchronize_session=False)
            db.query(LegacyMigrationSync).delete(synchronize_session=False)

            # Delete catalog tables
            db.query(Product).delete(synchronize_session=False)
            db.query(Partner).delete(synchronize_session=False)

            db.commit()

            # Ensure basic chart of accounts and causals
            seed_chart_of_accounts(db)
            seed_default_accounting_causals(db)

            return {
                "status": "success",
                "message": "Database operativo azzerato con successo. Account utenti preservati."
            }
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Errore durante il reset del database: {str(e)}")

