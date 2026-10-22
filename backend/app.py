from gevent import monkey
monkey.patch_all()

from flask import Flask, jsonify, request, Response
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, create_access_token
from flask_cors import CORS # Needed for the frontend to talk to the backend
import os
import io
import csv
from models import db, User, Partner, Product, DeliveryNote, DeliveryNoteItem, Invoice, InvoiceItem, InvoiceInstallment, Account, JournalEntry, JournalItem, CustomerOrder, OrderItem, PurchaseDeliveryNote, PurchaseDeliveryNoteItem, PalletType, PalletReceipt, PalletReceiptItem, CmrDocument, CmrItem, EventChannel, EventCategory, EventType, SystemEvent
from sqlalchemy import text
from sqlalchemy import inspect, func
from datetime import datetime, date, timedelta
import calendar
import re
from functools import wraps
from flask_socketio import SocketIO, emit
from services.sdi_service import generate_sdi_xml, validate_sdi_invoice
from services.event_dispatcher import dispatch_event, seed_default_channels_and_categories, get_redis_connection

app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "super-secret-key")
jwt = JWTManager(app)
CORS(app)
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='gevent',
    message_queue='redis://redis:6379/0',
    resource_path='/api/socket.io', # Deve coincidere con il path del frontend
    path='/api/socket.io'           # Per sicurezza impostiamo entrambi
)

DB_TYPE = os.environ.get('DB_TYPE', 'sqlite')
if DB_TYPE in ('postgres', 'postgresql'):
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url.startswith('postgresql://') and not db_url.startswith('postgresql+'):
        db_url = db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

db.init_app(app)
migrate = Migrate(app, db)

def get_request_identity():
    email = request.headers.get('X-Forwarded-Email')
    username = request.headers.get('X-Forwarded-Preferred-Username') or request.headers.get('X-Forwarded-User')
    groups_header = request.headers.get('X-Forwarded-Groups', '')
    groups = [g.strip() for g in groups_header.split(',') if g.strip()]

    # Fallback per ambiente di sviluppo locale se non dietro proxy
    if not email and os.environ.get('FLASK_ENV') == 'development' and not app.config.get('TESTING'):
        email = os.environ.get('DEV_AUTH_USER', 'dev@example.com')
        username = username or 'dev'
        groups = [os.environ.get('DEV_AUTH_ROLE', 'Admin')]

    return email, username, groups

def require_auth(roles=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            email, _, _ = get_request_identity()
            if not email:
                return jsonify({"error": "Unauthorized"}), 401
            user = User.query.filter_by(email=email).first()
            if not user:
                return jsonify({"error": "User not registered"}), 401
            if roles and user.role not in roles:
                return jsonify({"error": "Forbidden: insufficient permissions"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/api/me', methods=['GET'])
def get_me():
    email, username, groups = get_request_identity()
    if not email:
        return jsonify({"authenticated": False, "error": "No identity found"}), 401

    username = username or email.split('@')[0]
    user = User.query.filter_by(email=email).first()
    if not user:
        is_admin = any('admin' in g.lower() for g in groups)
        role = 'Admin' if is_admin else 'User'
        user = User(username=username, email=email, role=role, oauth_provider='oidc')
        db.session.add(user)
        try:
            db.session.commit()
            broadcast_users()
        except IntegrityError:
            db.session.rollback()
            user = User.query.filter_by(email=email).first()

    return jsonify({
        "authenticated": True,
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "role": getattr(user, 'role', 'User')
    }), 200

# ==========================================
# GESTIONE MODULI & FEATURE FLAGS
# ==========================================
AVAILABLE_MODULES = ["anagrafiche", "orders", "delivery_notes", "invoicing", "accounting", "warehouse", "pallets", "cmr"]

def is_module_enabled(module_name):
    enabled = os.getenv('ENABLED_MODULES', 'all').strip().lower()
    if enabled == 'all' or not enabled:
        return True
    active_set = {m.strip().lower() for m in enabled.split(',')}
    return module_name.lower() in active_set

@app.route('/api/modules', methods=['GET'])
def get_enabled_modules():
    return jsonify({
        mod: is_module_enabled(mod) for mod in AVAILABLE_MODULES
    }), 200

@app.route('/api/data')
def get_data():
    return {"message": "Hello from Flask!"}

@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify({"message": "Hello from the Flask backend!", "status": "success"})

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    email = data.get('email')
    
    # 1. Check if email format is valid
    if not re.match(EMAIL_REGEX, email):
        return jsonify({"error": "Invalid email format"}), 400
    
    # 2. Check if user already exists
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists"}), 400
    
    user = User(username=email, email=email)
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "Account created successfully"}), 201

@app.route('/api/signin', methods=['POST'])
def signin():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({"msg": "Email and password are required"}), 400
    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        token = create_access_token(identity=user.email)
        return jsonify(access_token=token), 200
    return jsonify({"msg": "Bad email or password"}), 401

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if user and user.check_password(data['password']):
        # In a real app, you'd return a JWT or set a session cookie
        return jsonify({"message": "Logged in", "user": user.email}), 200
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json
    user = User.query.filter_by(email=data.get('email')).first()
    
    if user:
        token = user.get_reset_token()
        db.session.commit()
        # In production, you would trigger an email here:
        print(f"DEBUG: Send email to {user.email} with link: http://localhost:5173/reset-password/{token}")
    
    # We return "Success" even if user isn't found for security (prevents email harvesting)
    return jsonify({"message": "If an account exists, a reset link has been sent."}), 200

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    user = User.query.filter_by(reset_token=data.get('token')).first()

    if not user or user.reset_token_expiry < datetime.utcnow():
        return jsonify({"error": "Invalid or expired token"}), 400

    user.set_password(data.get('new_password'))
    user.reset_token = None # Clear token after use
    user.reset_token_expiry = None
    db.session.commit()
    return jsonify({"message": "Password updated successfully"}), 200

def format_user(user):
    """Trasforma l'oggetto DB in dizionario sicuro per il frontend"""
    return {
        "id": user.id,
        "name": user.username,
        "username": user.username,
        "email": user.email,
        "role": getattr(user, 'role', 'User'),
        # Inviamo solo un booleano per il token, non il token stesso!
        "reset_token": True if user.reset_token else False,
        "reset_token_expiry": user.reset_token_expiry.isoformat() if user.reset_token_expiry else None
    }

def broadcast_users():
    try:
        users_all = User.query.all()
        data = [format_user(u) for u in users_all]
        socketio.emit('users_update', data)
    except Exception as e:
        print(f"Socket broadcast error: {e}")

@socketio.on('get_users')
def handle_get_users():
    users_all = User.query.all() # Esempio SQLAlchemy
    data = [format_user(u) for u in users_all]
    emit('users_update', data)


from sqlalchemy.exc import IntegrityError

@app.route('/api/users', methods=['GET', 'POST'])
@app.route('/api/users/<int:uid>', methods=['PUT', 'DELETE'])
def user_service(uid=None):
    if request.method == 'GET':
        users = User.query.all()
        return jsonify([{
            "id": u.id, 
            "name": u.username,
            "email": u.email,
            "role": getattr(u, 'role', 'User') # Safe access
        } for u in users])

    if request.method == 'DELETE' and uid:
        user = User.query.get_or_404(uid)
        db.session.delete(user)
    else:
        data = request.get_json() or {}
        user = User.query.get(uid) if uid else User()
        
        # Map frontend 'name' to backend 'username'
        if 'name' in data: user.username = data['name']
        if 'email' in data: user.email = data['email']
        
        # Only try to set role if the column actually exists in your DB
        if 'role' in data and hasattr(User, 'role'): 
            user.role = data['role']
        
        if not uid:
            # Set a dummy password if one isn't provided to satisfy constraints
            user.set_password(data.get('password', 'Default123!'))
            db.session.add(user)

    try:
        db.session.commit()
        broadcast_users()
        return jsonify({"message": "Success"}), (201 if not uid else 200)
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "User with this email or username already exists"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    

@app.route('/api/health', methods=['GET'])
def health_check():
    health_status = {
        "flask_status": "UP",
        "database": {
            "status": "DOWN",
            "type": os.environ.get('DB_TYPE', 'unknown'),
            "connection_error": None
        }
    }
    
    try:
        # This executes a simple query to verify the DB connection
        db.session.execute(text('SELECT 1'))
        health_status["database"]["status"] = "UP"
    except Exception as e:
        health_status["database"]["connection_error"] = str(e)
        
    return jsonify(health_status)

@app.route('/api/db-explorer', methods=['GET'])
@require_auth(roles=['Admin'])
def db_explorer():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    db_info = []
    for table_name in tables:
        # Dynamically get the row count for each table
        # We reflect the table to avoid hardcoding models
        res = db.session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
        
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        
        db_info.append({
            "name": table_name,
            "rows": res,
            "columns": columns
        })

    return jsonify({
        "engine": db.engine.name,
        "tables": db_info
    })

@app.route('/api/db-explorer/<table_name>/data', methods=['GET'])
@require_auth(roles=['Admin'])
def get_table_data(table_name):
    inspector = inspect(db.engine)
    if table_name not in inspector.get_table_names():
        return jsonify({"error": "Table not found"}), 404
    try:
        # Fetch the first 10 rows
        result = db.session.execute(text(f"SELECT * FROM {table_name} LIMIT 10"))
        
        # Get column names from the result keys
        columns = result.keys()
        
        # Convert rows to a list of dictionaries
        data = [dict(zip(columns, row)) for row in result]
        
        return jsonify({
            "columns": list(columns),
            "rows": data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# PARTNER / SOGGETTI COMMERCIALI
# ==========================================

@app.route('/api/partners', methods=['GET'])
@require_auth()
def get_partners():
    query = Partner.query
    tipo = request.args.get('tipo')
    if tipo and tipo != 'tutti':
        if tipo in ('cliente', 'fornitore', 'vettore'):
            query = query.filter((Partner.tipo == tipo) | (Partner.tipo == 'entrambi'))
        else:
            query = query.filter_by(tipo=tipo)
    
    search = request.args.get('search')
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Partner.ragione_sociale.ilike(search_filter)) |
            (Partner.partita_iva.ilike(search_filter)) |
            (Partner.citta.ilike(search_filter))
        )

    attivo = request.args.get('attivo')
    if attivo is not None:
        is_attivo = attivo.lower() in ('true', '1')
        query = query.filter_by(attivo=is_attivo)

    partners = query.order_by(Partner.ragione_sociale.asc()).all()
    return jsonify([p.to_dict() for p in partners]), 200

@app.route('/api/partners', methods=['POST'])
@require_auth(roles=['Admin'])
def create_partner():
    data = request.get_json() or {}
    if not data.get('ragione_sociale'):
        return jsonify({"error": "ragione_sociale is required"}), 400

    partner = Partner(
        ragione_sociale=data.get('ragione_sociale'),
        tipo=data.get('tipo', 'cliente'),
        partita_iva=data.get('partita_iva'),
        codice_fiscale=data.get('codice_fiscale'),
        indirizzo=data.get('indirizzo'),
        cap=data.get('cap'),
        citta=data.get('citta'),
        provincia=data.get('provincia'),
        nazione=data.get('nazione', 'IT'),
        codice_sdi=data.get('codice_sdi', '0000000'),
        pec=data.get('pec'),
        istituto_certificatore=data.get('istituto_certificatore'),
        iban=data.get('iban'),
        condizioni_pagamento=data.get('condizioni_pagamento', '30gg fm'),
        attivo=data.get('attivo', True)
    )
    db.session.add(partner)
    try:
        db.session.commit()
        return jsonify(partner.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/partners/<int:pid>', methods=['PUT'])
@require_auth(roles=['Admin'])
def update_partner(pid):
    partner = db.session.get(Partner, pid)
    if not partner:
        return jsonify({"error": "Partner not found"}), 404
    data = request.get_json() or {}
    
    for key, value in data.items():
        if hasattr(partner, key) and key != 'id':
            setattr(partner, key, value)

    try:
        db.session.commit()
        return jsonify(partner.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/partners/<int:pid>', methods=['DELETE'])
@require_auth(roles=['Admin'])
def delete_partner(pid):
    partner = db.session.get(Partner, pid)
    if not partner:
        return jsonify({"error": "Partner not found"}), 404
    partner.attivo = False
    try:
        db.session.commit()
        return jsonify({"message": "Partner deactivated"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

# ==========================================
# PRODUCT / CATALOGO ARTICOLI
# ==========================================

@app.route('/api/products', methods=['GET'])
@require_auth()
def get_products():
    query = Product.query
    categoria = request.args.get('categoria')
    if categoria and categoria != 'tutti':
        query = query.filter_by(categoria=categoria)

    in_scadenza = request.args.get('in_scadenza')
    if in_scadenza is not None:
        query = query.filter_by(in_scadenza=in_scadenza.lower() in ('true', '1'))

    search = request.args.get('search')
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Product.codice.ilike(search_filter)) |
            (Product.descrizione.ilike(search_filter))
        )

    attivo = request.args.get('attivo')
    if attivo is not None:
        query = query.filter_by(attivo=attivo.lower() in ('true', '1'))

    products = query.order_by(Product.codice.asc()).all()
    return jsonify([p.to_dict() for p in products]), 200

@app.route('/api/products', methods=['POST'])
@require_auth(roles=['Admin'])
def create_product():
    data = request.get_json() or {}
    codice = data.get('codice')
    descrizione = data.get('descrizione')
    if not codice or not descrizione:
        return jsonify({"error": "codice and descrizione are required"}), 400

    if Product.query.filter_by(codice=codice).first():
        return jsonify({"error": f"Product with code '{codice}' already exists"}), 400

    product = Product(
        codice=codice,
        descrizione=descrizione,
        descrizione_en=data.get('descrizione_en'),
        categoria=data.get('categoria', 'fresco'),
        unita_misura=data.get('unita_misura', 'KG'),
        peso_netto=float(data.get('peso_netto', 0.0)),
        peso_lordo=float(data.get('peso_lordo', 0.0)),
        tara=float(data.get('tara', 0.0)),
        in_scadenza=bool(data.get('in_scadenza', False)),
        scorta_minima=float(data.get('scorta_minima', 0.0)),
        prezzo_vendita=float(data.get('prezzo_vendita', 0.0)),
        prezzo_acquisto=float(data.get('prezzo_acquisto', 0.0)),
        aliquota_iva=int(data.get('aliquota_iva', 4)),
        codice_nc=data.get('codice_nc'),
        attivo=data.get('attivo', True)
    )
    db.session.add(product)
    try:
        db.session.commit()
        return jsonify(product.to_dict()), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": f"Product with code '{codice}' already exists"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/products/<int:pid>', methods=['PUT'])
@require_auth(roles=['Admin'])
def update_product(pid):
    product = db.session.get(Product, pid)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    data = request.get_json() or {}

    for key, value in data.items():
        if hasattr(product, key) and key != 'id':
            if key in ('peso_netto', 'peso_lordo', 'tara', 'scorta_minima', 'prezzo_vendita', 'prezzo_acquisto'):
                value = float(value)
            elif key == 'aliquota_iva':
                value = int(value)
            setattr(product, key, value)

    try:
        db.session.commit()
        return jsonify(product.to_dict()), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Product code already exists"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/products/<int:pid>', methods=['DELETE'])
@require_auth(roles=['Admin'])
def delete_product(pid):
    product = db.session.get(Product, pid)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    product.attivo = False
    try:
        db.session.commit()
        return jsonify({"message": "Product deactivated"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

# ==========================================
# BOLLETTAZIONE / DDT (DOCUMENTI DI TRASPORTO)
# ==========================================

def get_next_ddt_number(anno):
    max_num = db.session.query(func.max(DeliveryNote.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

@app.route('/api/delivery-notes', methods=['GET'])
@require_auth()
def get_delivery_notes():
    query = DeliveryNote.query
    stato = request.args.get('stato')
    if stato and stato != 'tutti':
        query = query.filter_by(stato=stato)

    cliente_id = request.args.get('cliente_id')
    if cliente_id:
        query = query.filter_by(cliente_id=int(cliente_id))

    anno = request.args.get('anno')
    if anno:
        query = query.filter_by(anno=int(anno))

    search = request.args.get('search')
    if search:
        search_filter = f"%{search}%"
        query = query.join(DeliveryNote.cliente).filter(
            (DeliveryNote.numero_completo.ilike(search_filter)) |
            (Partner.ragione_sociale.ilike(search_filter))
        )

    ddts = query.order_by(DeliveryNote.data_documento.desc(), DeliveryNote.numero.desc()).all()
    return jsonify([d.to_dict() for d in ddts]), 200

@app.route('/api/delivery-notes/<int:did>', methods=['GET'])
@require_auth()
def get_delivery_note_detail(did):
    ddt = db.session.get(DeliveryNote, did)
    if not ddt:
        return jsonify({"error": "Delivery note not found"}), 404
    return jsonify(ddt.to_dict()), 200

@app.route('/api/delivery-notes', methods=['POST'])
@require_auth(roles=['Admin'])
def create_delivery_note():
    data = request.get_json() or {}
    cliente_id = data.get('cliente_id')
    if not cliente_id:
        return jsonify({"error": "cliente_id is required"}), 400

    cliente = db.session.get(Partner, cliente_id)
    if not cliente:
        return jsonify({"error": "Cliente partner not found"}), 400

    items_data = data.get('items', [])
    if not items_data:
        return jsonify({"error": "At least one item is required in delivery note"}), 400

    doc_date_str = data.get('data_documento')
    if doc_date_str:
        doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date()
    else:
        doc_date = date.today()

    anno = doc_date.year
    numero = get_next_ddt_number(anno)
    numero_completo = f"DDT-{anno}-{numero:04d}"

    colli_totali = 0
    peso_totale_netto = 0.0
    peso_totale_lordo = 0.0
    totale_imponibile = 0.0

    ddt_items = []
    for idx, item in enumerate(items_data):
        prod_id = item.get('product_id')
        if not prod_id:
            return jsonify({"error": f"Item {idx+1}: product_id is required"}), 400
        product = db.session.get(Product, prod_id)
        if not product:
            return jsonify({"error": f"Item {idx+1}: product not found"}), 400

        colli = int(item.get('colli', 1))
        quantita = float(item.get('quantita', 1.0))
        prezzo_unitario = float(item.get('prezzo_unitario', product.prezzo_vendita))
        aliquota_iva = int(item.get('aliquota_iva', product.aliquota_iva))
        descrizione = item.get('descrizione', product.descrizione)
        unita_misura = item.get('unita_misura', product.unita_misura)
        lotto = item.get('lotto')
        data_scadenza_str = item.get('data_scadenza')

        # Controllo tracciabilità biologica (ReteBio standard)
        if product.in_scadenza:
            if not lotto or not data_scadenza_str:
                return jsonify({"error": f"Prodotto biologico in scadenza '{product.descrizione}': lotto e data di scadenza sono obbligatori!"}), 400

        data_scadenza = datetime.strptime(data_scadenza_str, '%Y-%m-%d').date() if data_scadenza_str else None

        colli_totali += colli
        if unita_misura.upper() == 'KG':
            peso_netto_riga = quantita
        else:
            peso_netto_riga = quantita * (product.peso_netto or 1.0)
        peso_totale_netto += peso_netto_riga
        peso_totale_lordo += peso_netto_riga + (colli * (product.tara or 0.0))
        totale_imponibile += (quantita * prezzo_unitario)

        ddt_item = DeliveryNoteItem(
            product_id=product.id,
            descrizione=descrizione,
            unita_misura=unita_misura,
            colli=colli,
            quantita=quantita,
            prezzo_unitario=prezzo_unitario,
            aliquota_iva=aliquota_iva,
            lotto=lotto,
            data_scadenza=data_scadenza
        )
        ddt_items.append(ddt_item)

    ddt = DeliveryNote(
        numero=numero,
        anno=anno,
        numero_completo=numero_completo,
        data_documento=doc_date,
        cliente_id=cliente.id,
        vettore_id=data.get('vettore_id'),
        causale_trasporto=data.get('causale_trasporto', 'Vendita'),
        porto=data.get('porto', 'Franco'),
        aspetto_beni=data.get('aspetto_beni', 'Colli'),
        colli_totali=colli_totali,
        peso_totale_netto=round(peso_totale_netto, 2),
        peso_totale_lordo=round(peso_totale_lordo, 2),
        totale_imponibile=round(totale_imponibile, 2),
        stato='bozza',
        note=data.get('note'),
        items=ddt_items
    )
    db.session.add(ddt)
    try:
        db.session.commit()
        return jsonify(ddt.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/delivery-notes/<int:did>', methods=['PUT'])
@require_auth(roles=['Admin'])
def update_delivery_note(did):
    ddt = db.session.get(DeliveryNote, did)
    if not ddt:
        return jsonify({"error": "Delivery note not found"}), 404
    if ddt.stato != 'bozza':
        return jsonify({"error": f"Impossibile modificare un DDT in stato '{ddt.stato}'"}), 400

    data = request.get_json() or {}
    for key in ('vettore_id', 'causale_trasporto', 'porto', 'aspetto_beni', 'note'):
        if key in data:
            setattr(ddt, key, data[key])

    try:
        db.session.commit()
        return jsonify(ddt.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/delivery-notes/<int:did>', methods=['DELETE'])
@require_auth(roles=['Admin'])
def delete_delivery_note(did):
    ddt = db.session.get(DeliveryNote, did)
    if not ddt:
        return jsonify({"error": "Delivery note not found"}), 404
    if ddt.stato != 'bozza':
        return jsonify({"error": f"Impossibile eliminare un DDT in stato '{ddt.stato}'"}), 400

    try:
        db.session.delete(ddt)
        db.session.commit()
        return jsonify({"message": "Delivery note deleted"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/delivery-notes/<int:did>/confirm', methods=['POST'])
@require_auth(roles=['Admin'])
def confirm_delivery_note(did):
    ddt = db.session.get(DeliveryNote, did)
    if not ddt:
        return jsonify({"error": "Delivery note not found"}), 404
    if not ddt.items:
        return jsonify({"error": "Impossibile confermare un DDT senza righe merce"}), 400

    ddt.stato = 'confermato'
    try:
        db.session.commit()
        return jsonify(ddt.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

# ==========================================
# FATTURAZIONE ATTIVA & SCADENZARIO
# ==========================================

def get_next_invoice_number(anno):
    max_num = db.session.query(func.max(Invoice.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

def calculate_installments(totale_fattura, data_documento, condizioni):
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
            # Ultima rata: pareggio al centesimo per quadratura contabile perfetta
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

@app.route('/api/delivery-notes/unbilled', methods=['GET'])
@require_auth()
def get_unbilled_delivery_notes():
    query = DeliveryNote.query.filter_by(stato='confermato')
    cliente_id = request.args.get('cliente_id')
    if cliente_id:
        query = query.filter_by(cliente_id=int(cliente_id))
    ddts = query.order_by(DeliveryNote.data_documento.asc(), DeliveryNote.numero.asc()).all()
    return jsonify([d.to_dict() for d in ddts]), 200

@app.route('/api/invoices/from-ddt', methods=['POST'])
@require_auth(roles=['Admin'])
def create_invoice_from_ddt():
    data = request.get_json() or {}
    cliente_id = data.get('cliente_id')
    ddt_ids = data.get('ddt_ids', [])
    if not cliente_id or not ddt_ids:
        return jsonify({"error": "cliente_id e ddt_ids sono obbligatori"}), 400

    cliente = db.session.get(Partner, cliente_id)
    if not cliente:
        return jsonify({"error": "Cliente non trovato"}), 404

    ddts = DeliveryNote.query.filter(DeliveryNote.id.in_(ddt_ids)).all()
    if len(ddts) != len(ddt_ids):
        return jsonify({"error": "Uno o più DDT non trovati"}), 404

    for d in ddts:
        if d.cliente_id != cliente.id:
            return jsonify({"error": f"DDT {d.numero_completo} non appartiene a questo cliente"}), 400
        if d.stato != 'confermato':
            return jsonify({"error": f"DDT {d.numero_completo} non è in stato confermato (stato: {d.stato})"}), 400

    doc_date_str = data.get('data_documento')
    doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()
    anno = doc_date.year
    numero = get_next_invoice_number(anno)
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

    rate_data = calculate_installments(totale_fattura, doc_date, condizioni)
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
    db.session.add(invoice)

    # Aggiorna lo stato dei DDT inclusi a 'fatturato'
    for ddt in ddts:
        ddt.stato = 'fatturato'

    try:
        db.session.commit()
        return jsonify(invoice.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/invoices', methods=['POST'])
@require_auth(roles=['Admin'])
def create_invoice_direct():
    data = request.get_json() or {}
    cliente_id = data.get('cliente_id')
    if not cliente_id:
        return jsonify({"error": "cliente_id is required"}), 400

    cliente = db.session.get(Partner, cliente_id)
    if not cliente:
        return jsonify({"error": "Cliente non trovato"}), 404

    items_data = data.get('items', [])
    if not items_data:
        return jsonify({"error": "At least one item is required"}), 400

    doc_date_str = data.get('data_documento')
    doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()
    anno = doc_date.year
    numero = get_next_invoice_number(anno)
    numero_completo = f"FT-{anno}-{numero:04d}"

    condizioni = data.get('condizioni_pagamento', cliente.condizioni_pagamento or '30gg fm')

    totale_imponibile = 0.0
    totale_imposta = 0.0
    castelletto = {}
    invoice_items = []

    for item in items_data:
        prod_id = item.get('product_id')
        product = db.session.get(Product, prod_id) if prod_id else None
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
            data_scadenza=datetime.strptime(item.get('data_scadenza'), '%Y-%m-%d').date() if item.get('data_scadenza') else None
        )
        invoice_items.append(inv_item)

    totale_imponibile = round(totale_imponibile, 2)
    totale_imposta = round(totale_imposta, 2)
    totale_fattura = round(totale_imponibile + totale_imposta, 2)

    rate_data = calculate_installments(totale_fattura, doc_date, condizioni)
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
        tipo_documento='TD01',
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
    db.session.add(invoice)
    try:
        db.session.commit()
        return jsonify(invoice.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/invoices', methods=['GET'])
@require_auth()
def get_invoices():
    query = Invoice.query
    stato = request.args.get('stato')
    if stato and stato != 'tutti':
        query = query.filter_by(stato=stato)

    tipo = request.args.get('tipo')
    if tipo and tipo != 'tutti':
        query = query.filter_by(tipo_documento=tipo)

    cliente_id = request.args.get('cliente_id')
    if cliente_id:
        query = query.filter_by(cliente_id=int(cliente_id))

    anno = request.args.get('anno')
    if anno:
        query = query.filter_by(anno=int(anno))

    search = request.args.get('search')
    if search:
        search_filter = f"%{search}%"
        query = query.join(Invoice.cliente).filter(
            (Invoice.numero_completo.ilike(search_filter)) |
            (Partner.ragione_sociale.ilike(search_filter))
        )

    invoices = query.order_by(Invoice.data_documento.desc(), Invoice.numero.desc()).all()
    return jsonify([inv.to_dict() for inv in invoices]), 200

def get_next_credit_note_number(anno):
    max_num = db.session.query(func.max(Invoice.numero))\
        .filter(Invoice.anno == anno, Invoice.tipo_documento == 'TD04')\
        .scalar()
    return (max_num or 0) + 1

@app.route('/api/invoices/<int:iid>/credit-note', methods=['POST'])
@require_auth(roles=['Admin'])
def create_credit_note_from_invoice(iid):
    inv = db.session.get(Invoice, iid)
    if not inv:
        return jsonify({"error": "Fattura d'origine non trovata"}), 404
    if inv.tipo_documento == 'TD04':
        return jsonify({"error": "Impossibile emettere una nota di credito a storno di un'altra nota di credito"}), 400

    data = request.get_json() or {}
    items_to_reverse = data.get('items', [])
    if not items_to_reverse:
        return jsonify({"error": "Almeno una riga da stornare richiesta"}), 400

    today = date.today()
    anno = today.year
    numero = get_next_credit_note_number(anno)
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
            return jsonify({"error": f"Riga fattura {orig_item_id} non trovata"}), 400

        qta_storno = float(it_rev.get('quantita_stornata', orig_item.quantita))
        if qta_storno <= 0 or qta_storno > orig_item.quantita:
            return jsonify({"error": f"Quantità da stornare non valida ({qta_storno})"}), 400

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
            db.session.add(p_reso)

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
    db.session.add(nc)

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

    try:
        db.session.commit()
        return jsonify(nc.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/invoices/<int:iid>', methods=['GET'])
@require_auth()
def get_invoice_detail(iid):
    invoice = db.session.get(Invoice, iid)
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    return jsonify(invoice.to_dict()), 200

@app.route('/api/invoices/<int:iid>/sdi-validate', methods=['GET'])
@require_auth()
def sdi_validate_invoice_endpoint(iid):
    invoice = db.session.get(Invoice, iid)
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    val_res = validate_sdi_invoice(invoice)
    return jsonify(val_res), 200

@app.route('/api/invoices/<int:iid>/xml', methods=['GET'])
@require_auth()
def download_sdi_xml_endpoint(iid):
    invoice = db.session.get(Invoice, iid)
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    try:
        xml_content, filename = generate_sdi_xml(invoice)
        response = Response(xml_content, mimetype='application/xml; charset=utf-8')
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/installments', methods=['GET'])
@require_auth()
def get_installments():
    query = InvoiceInstallment.query
    stato = request.args.get('stato')
    if stato and stato != 'tutti':
        query = query.filter_by(stato=stato)

    installments = query.order_by(InvoiceInstallment.data_scadenza.asc()).all()
    return jsonify([inst.to_dict() for inst in installments]), 200

@app.route('/api/installments/<int:inst_id>/pay', methods=['POST'])
@require_auth(roles=['Admin'])
def pay_installment(inst_id):
    inst = db.session.get(InvoiceInstallment, inst_id)
    if not inst:
        return jsonify({"error": "Installment not found"}), 404

    inst.stato = 'incassata'
    inst.data_incasso = date.today()

    # Controlla se tutte le rate della fattura sono incassate
    invoice = inst.invoice
    if all(i.stato == 'incassata' for i in invoice.installments):
        invoice.stato = 'saldata'

    try:
        db.session.commit()
        return jsonify(inst.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

# ==========================================
# CONTABILITÀ GENERALE, PRIMA NOTA & REPORT
# ==========================================

def get_next_journal_entry_number(anno):
    max_num = db.session.query(func.max(JournalEntry.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

@app.route('/api/accounting/accounts', methods=['GET'])
@require_auth()
def get_accounts():
    accounts = Account.query.order_by(Account.codice.asc()).all()
    return jsonify([a.to_dict() for a in accounts]), 200

@app.route('/api/accounting/accounts', methods=['POST'])
@require_auth(roles=['Admin'])
def create_account():
    data = request.get_json() or {}
    codice = data.get('codice')
    nome = data.get('nome')
    tipo = data.get('tipo')
    if not codice or not nome or not tipo:
        return jsonify({"error": "codice, nome e tipo sono obbligatori"}), 400
    if Account.query.filter_by(codice=codice).first():
        return jsonify({"error": f"Conto con codice {codice} già esistente"}), 400
    acc = Account(codice=codice, nome=nome, tipo=tipo, attivo=data.get('attivo', True))
    db.session.add(acc)
    db.session.commit()
    return jsonify(acc.to_dict()), 201

@app.route('/api/accounting/entries', methods=['GET'])
@require_auth()
def get_journal_entries():
    query = JournalEntry.query
    anno = request.args.get('anno')
    if anno:
        query = query.filter_by(anno=int(anno))
    search = request.args.get('search')
    if search:
        query = query.filter(JournalEntry.causale.ilike(f"%{search}%"))
    entries = query.order_by(JournalEntry.data_registrazione.desc(), JournalEntry.numero.desc()).all()
    return jsonify([e.to_dict() for e in entries]), 200

@app.route('/api/accounting/entries/<int:eid>', methods=['GET'])
@require_auth()
def get_journal_entry_detail(eid):
    entry = db.session.get(JournalEntry, eid)
    if not entry:
        return jsonify({"error": "Registrazione non trovata"}), 404
    return jsonify(entry.to_dict()), 200

@app.route('/api/accounting/entries', methods=['POST'])
@require_auth(roles=['Admin'])
def create_journal_entry():
    data = request.get_json() or {}
    causale = data.get('causale')
    items_data = data.get('items', [])
    if not causale:
        return jsonify({"error": "causale is required"}), 400
    if len(items_data) < 2:
        return jsonify({"error": "La scrittura di prima nota richiede almeno due righe contabili"}), 400

    totale_dare = 0.0
    totale_avere = 0.0
    journal_items = []

    for it in items_data:
        acc_id = it.get('account_id')
        dare = round(float(it.get('dare', 0.0)), 2)
        avere = round(float(it.get('avere', 0.0)), 2)
        if not acc_id:
            return jsonify({"error": "account_id obbligatorio per ciascuna riga"}), 400
        totale_dare += dare
        totale_avere += avere
        journal_items.append(JournalItem(
            account_id=acc_id,
            partner_id=it.get('partner_id'),
            dare=dare,
            avere=avere,
            descrizione_riga=it.get('descrizione_riga')
        ))

    totale_dare = round(totale_dare, 2)
    totale_avere = round(totale_avere, 2)

    # VINCOLO BLOCCANTE PARTITA DOPPIA A PAREGGIO
    if abs(totale_dare - totale_avere) > 0.001:
        return jsonify({"error": f"Scrittura sbilanciata! Il totale Dare (€ {totale_dare}) non coincide con il totale Avere (€ {totale_avere})"}), 400

    doc_date_str = data.get('data_registrazione')
    doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()
    comp_date_str = data.get('data_competenza')
    comp_date = datetime.strptime(comp_date_str, '%Y-%m-%d').date() if comp_date_str else doc_date

    anno = doc_date.year
    numero = get_next_journal_entry_number(anno)
    numero_completo = f"PN-{anno}-{numero:04d}"

    entry = JournalEntry(
        numero=numero,
        anno=anno,
        numero_completo=numero_completo,
        data_registrazione=doc_date,
        data_competenza=comp_date,
        causale=causale,
        totale_dare=totale_dare,
        totale_avere=totale_avere,
        stato=data.get('stato', 'confermata'),
        note=data.get('note'),
        items=journal_items
    )
    db.session.add(entry)
    try:
        db.session.commit()
        return jsonify(entry.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/accounting/reports/libro-giornale', methods=['GET'])
@require_auth()
def report_libro_giornale():
    anno = request.args.get('anno')
    query = JournalEntry.query.filter_by(stato='confermata')
    if anno:
        query = query.filter_by(anno=int(anno))
    entries = query.order_by(JournalEntry.data_registrazione.asc(), JournalEntry.numero.asc()).all()

    righe = []
    tot_dare = 0.0
    tot_avere = 0.0

    for entry in entries:
        for it in entry.items:
            tot_dare += it.dare
            tot_avere += it.avere
            righe.append({
                "entry_id": entry.id,
                "data": entry.data_registrazione.isoformat(),
                "numero": entry.numero_completo,
                "causale": entry.causale,
                "account_codice": it.account.codice if it.account else "",
                "account_nome": it.account.nome if it.account else "",
                "partner_nome": it.partner.ragione_sociale if it.partner else "",
                "dare": it.dare,
                "avere": it.avere
            })

    tot_dare = round(tot_dare, 2)
    tot_avere = round(tot_avere, 2)

    if request.args.get('format') == 'csv':
        si = io.StringIO()
        cw = csv.writer(si, delimiter=';')
        cw.writerow(["Data", "Numero", "Causale", "Codice", "Conto", "Partner", "Dare", "Avere"])
        for r in righe:
            cw.writerow([r["data"], r["numero"], r["causale"], r["account_codice"], r["account_nome"], r["partner_nome"], f"{r['dare']:.2f}", f"{r['avere']:.2f}"])
        cw.writerow([])
        cw.writerow(["TOTALI", "", "", "", "", "", f"{tot_dare:.2f}", f"{tot_avere:.2f}"])
        output = si.getvalue()
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=libro_giornale.csv"})

    return jsonify({
        "anno": anno or date.today().year,
        "totale_dare": tot_dare,
        "totale_avere": tot_avere,
        "quadratura": round(tot_dare - tot_avere, 2) == 0.0,
        "righe": righe
    }), 200

@app.route('/api/accounting/reports/mastro', methods=['GET'])
@require_auth()
def report_mastro():
    account_id = request.args.get('account_id')
    if not account_id:
        return jsonify({"error": "account_id is required"}), 400
    account = db.session.get(Account, int(account_id))
    if not account:
        return jsonify({"error": "Account not found"}), 404

    partner_id = request.args.get('partner_id')
    query = JournalItem.query.join(JournalEntry).filter(
        JournalItem.account_id == account.id,
        JournalEntry.stato == 'confermata'
    )
    if partner_id:
        query = query.filter(JournalItem.partner_id == int(partner_id))

    items = query.order_by(JournalEntry.data_registrazione.asc(), JournalEntry.numero.asc()).all()

    saldo_progressivo = 0.0
    movimenti = []
    tot_dare = 0.0
    tot_avere = 0.0

    for it in items:
        tot_dare += it.dare
        tot_avere += it.avere
        if account.tipo in ['attivo', 'costi']:
            saldo_progressivo += (it.dare - it.avere)
        else:
            saldo_progressivo += (it.avere - it.dare)

        movimenti.append({
            "id": it.id,
            "data": it.entry.data_registrazione.isoformat(),
            "numero": it.entry.numero_completo,
            "causale": it.entry.causale,
            "partner_nome": it.partner.ragione_sociale if it.partner else None,
            "dare": it.dare,
            "avere": it.avere,
            "saldo_progressivo": round(saldo_progressivo, 2)
        })

    tot_dare = round(tot_dare, 2)
    tot_avere = round(tot_avere, 2)
    saldo_finale = round(saldo_progressivo, 2)

    if request.args.get('format') == 'csv':
        si = io.StringIO()
        cw = csv.writer(si, delimiter=';')
        cw.writerow(["Estratto Conto Mastro", f"{account.codice} - {account.nome} ({account.tipo})"])
        cw.writerow(["Data", "Numero", "Causale", "Partner", "Dare", "Avere", "Saldo Progressivo"])
        for m in movimenti:
            cw.writerow([m["data"], m["numero"], m["causale"], m["partner_nome"] or "", f"{m['dare']:.2f}", f"{m['avere']:.2f}", f"{m['saldo_progressivo']:.2f}"])
        cw.writerow([])
        cw.writerow(["TOTALI", "", "", "", f"{tot_dare:.2f}", f"{tot_avere:.2f}", f"SALDO FINALE: {saldo_finale:.2f}"])
        output = si.getvalue()
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=mastro_{account.codice}.csv"})

    return jsonify({
        "conto": account.to_dict(),
        "totale_dare": tot_dare,
        "totale_avere": tot_avere,
        "saldo_finale": saldo_finale,
        "movimenti": movimenti
    }), 200

@app.route('/api/accounting/reports/bilancio-verifica', methods=['GET'])
@require_auth()
def report_bilancio_verifica():
    anno = request.args.get('anno')
    accounts = Account.query.order_by(Account.codice.asc()).all()

    conti_report = []
    tot_dare_gen = 0.0
    tot_avere_gen = 0.0

    for acc in accounts:
        items_query = JournalItem.query.join(JournalEntry).filter(
            JournalItem.account_id == acc.id,
            JournalEntry.stato == 'confermata'
        )
        if anno:
            items_query = items_query.filter(JournalEntry.anno == int(anno))

        items = items_query.all()
        if not items:
            continue

        acc_dare = round(sum(it.dare for it in items), 2)
        acc_avere = round(sum(it.avere for it in items), 2)

        if acc.tipo in ['attivo', 'costi']:
            saldo_netto = round(acc_dare - acc_avere, 2)
        else:
            saldo_netto = round(acc_avere - acc_dare, 2)

        tot_dare_gen += acc_dare
        tot_avere_gen += acc_avere

        conti_report.append({
            "account_id": acc.id,
            "codice": acc.codice,
            "nome": acc.nome,
            "tipo": acc.tipo,
            "totale_dare": acc_dare,
            "totale_avere": acc_avere,
            "saldo_netto": saldo_netto
        })

    tot_dare_gen = round(tot_dare_gen, 2)
    tot_avere_gen = round(tot_avere_gen, 2)

    if request.args.get('format') == 'csv':
        si = io.StringIO()
        cw = csv.writer(si, delimiter=';')
        cw.writerow(["Codice", "Conto", "Mastro", "Totale Dare", "Totale Avere", "Saldo Netto"])
        for c in conti_report:
            cw.writerow([c["codice"], c["nome"], c["tipo"], f"{c['totale_dare']:.2f}", f"{c['totale_avere']:.2f}", f"{c['saldo_netto']:.2f}"])
        cw.writerow([])
        cw.writerow(["TOTALI A PAREGGIO", "", "", f"{tot_dare_gen:.2f}", f"{tot_avere_gen:.2f}", ""])
        output = si.getvalue()
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=bilancio_verifica.csv"})

    return jsonify({
        "anno": anno or date.today().year,
        "totale_dare": tot_dare_gen,
        "totale_avere": tot_avere_gen,
        "quadratura": round(tot_dare_gen - tot_avere_gen, 2) == 0.0,
        "conti": conti_report
    }), 200

# ==========================================
# SUPPLY CHAIN: CICLO ORDINI CLIENTI & EVASIONE
# ==========================================

def get_next_order_number(anno):
    max_num = db.session.query(func.max(CustomerOrder.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

@app.route('/api/orders', methods=['GET'])
@require_auth()
def get_orders():
    query = CustomerOrder.query
    stato = request.args.get('stato')
    if stato and stato != 'tutti':
        query = query.filter_by(stato=stato)
    cliente_id = request.args.get('cliente_id')
    if cliente_id:
        query = query.filter_by(cliente_id=int(cliente_id))
    anno = request.args.get('anno')
    if anno:
        query = query.filter_by(anno=int(anno))
    search = request.args.get('search')
    if search:
        search_filter = f"%{search}%"
        query = query.join(CustomerOrder.cliente).filter(
            (CustomerOrder.numero_completo.ilike(search_filter)) |
            (Partner.ragione_sociale.ilike(search_filter))
        )
    orders = query.order_by(CustomerOrder.data_ordine.desc(), CustomerOrder.numero.desc()).all()
    return jsonify([o.to_dict() for o in orders]), 200

@app.route('/api/orders/<int:oid>', methods=['GET'])
@require_auth()
def get_order_detail(oid):
    order = db.session.get(CustomerOrder, oid)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(order.to_dict()), 200

@app.route('/api/orders', methods=['POST'])
@require_auth(roles=['Admin'])
def create_order():
    data = request.get_json() or {}
    cliente_id = data.get('cliente_id')
    if not cliente_id:
        return jsonify({"error": "cliente_id is required"}), 400
    cliente = db.session.get(Partner, cliente_id)
    if not cliente:
        return jsonify({"error": "Cliente not found"}), 404

    items_data = data.get('items', [])
    if not items_data:
        return jsonify({"error": "At least one item is required"}), 400

    doc_date_str = data.get('data_ordine')
    doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()
    req_date_str = data.get('data_richiesta')
    req_date = datetime.strptime(req_date_str, '%Y-%m-%d').date() if req_date_str else None
    conf_date_str = data.get('data_confermata')
    conf_date = datetime.strptime(conf_date_str, '%Y-%m-%d').date() if conf_date_str else None

    anno = doc_date.year
    numero = get_next_order_number(anno)
    numero_completo = f"ORD-{anno}-{numero:04d}"

    totale_imponibile = 0.0
    order_items = []
    seq = 5

    for it in items_data:
        prod_id = it.get('product_id')
        product = db.session.get(Product, prod_id) if prod_id else None
        descrizione = it.get('descrizione', product.descrizione if product else 'Articolo')
        unita_misura = it.get('unita_misura', product.unita_misura if product else 'KG')
        colli = int(it.get('colli_ordinati', 1))
        qta = float(it.get('quantita_ordinata', 1.0))
        prezzo = float(it.get('prezzo_unitario', product.prezzo_vendita if product else 0.0))
        aliquota = int(it.get('aliquota_iva', product.aliquota_iva if product else 4))
        lotto = it.get('lotto')

        totale_imponibile += round(qta * prezzo, 2)

        riga_seq = int(it.get('sequenza', seq))
        seq = max(seq, riga_seq) + 5

        order_items.append(OrderItem(
            product_id=prod_id,
            sequenza=riga_seq,
            descrizione=descrizione,
            unita_misura=unita_misura,
            colli_ordinati=colli,
            quantita_ordinata=qta,
            colli_consegnati=0,
            quantita_consegnata=0.0,
            prezzo_unitario=prezzo,
            aliquota_iva=aliquota,
            lotto=lotto,
            stato='aperto'
        ))

    order = CustomerOrder(
        numero=numero,
        anno=anno,
        numero_completo=numero_completo,
        data_ordine=doc_date,
        data_richiesta=req_date,
        data_confermata=conf_date,
        cliente_id=cliente.id,
        stato='aperto',
        totale_imponibile=round(totale_imponibile, 2),
        note=data.get('note'),
        items=order_items
    )
    db.session.add(order)
    try:
        db.session.commit()
        return jsonify(order.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/orders/<int:oid>', methods=['PUT'])
@require_auth(roles=['Admin'])
def update_order(oid):
    order = db.session.get(CustomerOrder, oid)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    if order.stato == 'chiuso':
        return jsonify({"error": "Impossibile modificare un ordine chiuso"}), 400

    data = request.get_json() or {}
    if 'note' in data:
        order.note = data['note']
    if 'data_richiesta' in data:
        order.data_richiesta = datetime.strptime(data['data_richiesta'], '%Y-%m-%d').date() if data['data_richiesta'] else None
    if 'data_confermata' in data:
        order.data_confermata = datetime.strptime(data['data_confermata'], '%Y-%m-%d').date() if data['data_confermata'] else None

    try:
        db.session.commit()
        return jsonify(order.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/orders/<int:oid>/fulfill-to-ddt', methods=['POST'])
@require_auth(roles=['Admin'])
def fulfill_order_to_ddt(oid):
    order = db.session.get(CustomerOrder, oid)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    if order.stato == 'chiuso':
        return jsonify({"error": "L'ordine è già interamente chiuso"}), 400

    data = request.get_json() or {}
    items_to_fulfill = data.get('items', [])
    if not items_to_fulfill:
        items_to_fulfill = [
            {"order_item_id": it.id, "colli": it.colli_residui, "quantita": it.quantita_residua}
            for it in order.items if it.quantita_residua > 0
        ]

    ddt_date = date.today()
    ddt_anno = ddt_date.year
    ddt_num = get_next_ddt_number(ddt_anno)
    ddt_numero_completo = f"DDT-{ddt_anno}-{ddt_num:04d}"

    ddt_items = []
    totale_imponibile_ddt = 0.0
    colli_totali_ddt = 0
    peso_totale_netto_ddt = 0.0

    items_dict = {it.id: it for it in order.items}

    for fulfill_req in items_to_fulfill:
        it_id = fulfill_req.get('order_item_id')
        order_item = items_dict.get(it_id)
        if not order_item:
            continue

        qta_evasa = float(fulfill_req.get('quantita', order_item.quantita_residua))
        colli_evasi = int(fulfill_req.get('colli', order_item.colli_residui))
        if qta_evasa <= 0:
            continue

        order_item.quantita_consegnata = round(order_item.quantita_consegnata + qta_evasa, 2)
        order_item.colli_consegnati += colli_evasi

        if order_item.quantita_consegnata >= order_item.quantita_ordinata:
            order_item.stato = 'chiuso'

        imp_riga = round(qta_evasa * order_item.prezzo_unitario, 2)
        totale_imponibile_ddt += imp_riga
        colli_totali_ddt += colli_evasi
        peso_totale_netto_ddt += qta_evasa

        ddt_item = DeliveryNoteItem(
            product_id=order_item.product_id,
            descrizione=order_item.descrizione,
            unita_misura=order_item.unita_misura,
            colli=colli_evasi,
            quantita=qta_evasa,
            prezzo_unitario=order_item.prezzo_unitario,
            aliquota_iva=order_item.aliquota_iva,
            lotto=fulfill_req.get('lotto', order_item.lotto)
        )
        ddt_items.append(ddt_item)

    if not ddt_items:
        return jsonify({"error": "Nessuna quantità valida da evadere"}), 400

    ddt = DeliveryNote(
        numero=ddt_num,
        anno=ddt_anno,
        numero_completo=ddt_numero_completo,
        data_documento=ddt_date,
        cliente_id=order.cliente_id,
        causale_trasporto='Vendita',
        porto='Franco',
        aspetto_beni='Colli',
        colli_totali=colli_totali_ddt,
        peso_totale_netto=round(peso_totale_netto_ddt, 2),
        peso_totale_lordo=round(peso_totale_netto_ddt * 1.05, 2),
        totale_imponibile=round(totale_imponibile_ddt, 2),
        stato='confermato',
        note=f"Evasione da Ordine {order.numero_completo}",
        items=ddt_items
    )
    db.session.add(ddt)

    if all(it.stato == 'chiuso' for it in order.items):
        order.stato = 'chiuso'
    else:
        order.stato = 'in_lavorazione'

    try:
        db.session.commit()
        return jsonify({
            "order": order.to_dict(),
            "ddt": ddt.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

# ==========================================
# SUPPLY CHAIN: ENTRATA MERCI & GIACENZE FEFO
# ==========================================

@app.route('/api/purchases', methods=['GET'])
@require_auth()
def get_purchases():
    query = PurchaseDeliveryNote.query
    fornitore_id = request.args.get('fornitore_id')
    if fornitore_id:
        query = query.filter_by(fornitore_id=int(fornitore_id))
    search = request.args.get('search')
    if search:
        search_filter = f"%{search}%"
        query = query.join(PurchaseDeliveryNote.fornitore).filter(
            (PurchaseDeliveryNote.numero_documento_fornitore.ilike(search_filter)) |
            (Partner.ragione_sociale.ilike(search_filter))
        )
    purchases = query.order_by(PurchaseDeliveryNote.data_ricezione.desc(), PurchaseDeliveryNote.id.desc()).all()
    return jsonify([p.to_dict() for p in purchases]), 200

@app.route('/api/purchases/<int:pid>', methods=['GET'])
@require_auth()
def get_purchase_detail(pid):
    purchase = db.session.get(PurchaseDeliveryNote, pid)
    if not purchase:
        return jsonify({"error": "Purchase not found"}), 404
    return jsonify(purchase.to_dict()), 200

@app.route('/api/purchases', methods=['POST'])
@require_auth(roles=['Admin'])
def create_purchase():
    data = request.get_json() or {}
    fornitore_id = data.get('fornitore_id')
    num_doc = data.get('numero_documento_fornitore')
    if not fornitore_id or not num_doc:
        return jsonify({"error": "fornitore_id e numero_documento_fornitore sono obbligatori"}), 400

    supplier = db.session.get(Partner, fornitore_id)
    if not supplier:
        return jsonify({"error": "Fornitore non trovato"}), 404

    items_data = data.get('items', [])
    if not items_data:
        return jsonify({"error": "Almeno una riga merce richiesta"}), 400

    doc_date_str = data.get('data_documento')
    doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()
    ric_date_str = data.get('data_ricezione')
    ric_date = datetime.strptime(ric_date_str, '%Y-%m-%d').date() if ric_date_str else date.today()

    totale_imponibile = 0.0
    totale_colli = 0
    totale_peso_netto = 0.0
    purchase_items = []

    for it in items_data:
        prod_id = it.get('product_id')
        product = db.session.get(Product, prod_id) if prod_id else None
        if not product:
            return jsonify({"error": f"Prodotto ID {prod_id} non trovato"}), 404

        lotto = it.get('lotto')
        scadenza_str = it.get('data_scadenza')
        scadenza_date = datetime.strptime(scadenza_str, '%Y-%m-%d').date() if scadenza_str else None

        if product.in_scadenza:
            if not lotto or not str(lotto).strip():
                return jsonify({"error": f"Il lotto è obbligatorio per l'articolo biologico '{product.descrizione}'"}), 400
            if not scadenza_date:
                return jsonify({"error": f"La data di scadenza è obbligatoria per l'articolo biologico '{product.descrizione}'"}), 400

        colli = int(it.get('colli', 1))
        qta = float(it.get('quantita', 1.0))
        prezzo = float(it.get('prezzo_unitario', product.prezzo_acquisto if product else 0.0))
        aliquota = int(it.get('aliquota_iva', product.aliquota_iva if product else 4))

        if prezzo > 0:
            product.prezzo_acquisto = prezzo

        totale_imponibile += round(qta * prezzo, 2)
        totale_colli += colli
        totale_peso_netto += qta

        purchase_items.append(PurchaseDeliveryNoteItem(
            product_id=prod_id,
            descrizione=it.get('descrizione', product.descrizione),
            unita_misura=it.get('unita_misura', product.unita_misura),
            colli=colli,
            quantita=qta,
            prezzo_unitario=prezzo,
            aliquota_iva=aliquota,
            lotto=lotto,
            data_scadenza=scadenza_date
        ))

    purchase = PurchaseDeliveryNote(
        numero_documento_fornitore=num_doc,
        data_documento=doc_date,
        data_ricezione=ric_date,
        fornitore_id=supplier.id,
        colli_totali=totale_colli,
        peso_totale_netto=round(totale_peso_netto, 2),
        totale_imponibile=round(totale_imponibile, 2),
        note=data.get('note'),
        items=purchase_items
    )
    db.session.add(purchase)
    try:
        db.session.commit()
        return jsonify(purchase.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/warehouse/stock', methods=['GET'])
@require_auth()
def get_warehouse_stock():
    carichi = db.session.query(
        PurchaseDeliveryNoteItem.product_id,
        PurchaseDeliveryNoteItem.lotto,
        PurchaseDeliveryNoteItem.data_scadenza,
        func.sum(PurchaseDeliveryNoteItem.quantita).label('carico_kg'),
        func.sum(PurchaseDeliveryNoteItem.colli).label('carico_colli')
    ).group_by(
        PurchaseDeliveryNoteItem.product_id,
        PurchaseDeliveryNoteItem.lotto,
        PurchaseDeliveryNoteItem.data_scadenza
    ).all()

    scarichi = db.session.query(
        DeliveryNoteItem.product_id,
        DeliveryNoteItem.lotto,
        func.sum(DeliveryNoteItem.quantita).label('scarico_kg'),
        func.sum(DeliveryNoteItem.colli).label('scarico_colli')
    ).group_by(
        DeliveryNoteItem.product_id,
        DeliveryNoteItem.lotto
    ).all()
    scarichi_map = {(s.product_id, s.lotto): (s.scarico_kg or 0.0, s.scarico_colli or 0) for s in scarichi}

    stock_list = []
    today = date.today()
    for c in carichi:
        sc_kg, sc_colli = scarichi_map.get((c.product_id, c.lotto), (0.0, 0))
        giacenza_kg = round(float(c.carico_kg or 0.0) - float(sc_kg), 2)
        colli_disp = max(0, int(c.carico_colli or 0) - int(sc_colli))
        if giacenza_kg > 0:
            prod = db.session.get(Product, c.product_id)
            giorni_a_scadere = (c.data_scadenza - today).days if c.data_scadenza else None
            if giorni_a_scadere is not None:
                if giorni_a_scadere <= 0:
                    stato_scadenza = 'scaduto'
                elif giorni_a_scadere <= 15:
                    stato_scadenza = 'in_scadenza'
                else:
                    stato_scadenza = 'fresco'
            else:
                stato_scadenza = 'non_deperibile'

            stock_list.append({
                "product_id": c.product_id,
                "product_codice": prod.codice if prod else "",
                "product_descrizione": prod.descrizione if prod else "",
                "lotto": c.lotto,
                "data_scadenza": c.data_scadenza.isoformat() if c.data_scadenza else None,
                "giorni_a_scadere": giorni_a_scadere,
                "stato_scadenza": stato_scadenza,
                "giacenza_kg": giacenza_kg,
                "colli_disponibili": colli_disp
            })

    stock_list.sort(key=lambda s: (s['product_codice'], s['data_scadenza'] or '9999-12-31'))
    return jsonify(stock_list), 200

@app.route('/api/warehouse/fefo-suggestions', methods=['GET'])
@require_auth()
def get_fefo_suggestions():
    prod_id = request.args.get('product_id')
    if not prod_id:
        return jsonify({"error": "product_id is required"}), 400

    carichi = db.session.query(
        PurchaseDeliveryNoteItem.product_id,
        PurchaseDeliveryNoteItem.lotto,
        PurchaseDeliveryNoteItem.data_scadenza,
        func.sum(PurchaseDeliveryNoteItem.quantita).label('carico_kg'),
        func.sum(PurchaseDeliveryNoteItem.colli).label('carico_colli')
    ).filter_by(product_id=int(prod_id)).group_by(
        PurchaseDeliveryNoteItem.product_id,
        PurchaseDeliveryNoteItem.lotto,
        PurchaseDeliveryNoteItem.data_scadenza
    ).all()

    scarichi = db.session.query(
        DeliveryNoteItem.product_id,
        DeliveryNoteItem.lotto,
        func.sum(DeliveryNoteItem.quantita).label('scarico_kg'),
        func.sum(DeliveryNoteItem.colli).label('scarico_colli')
    ).filter_by(product_id=int(prod_id)).group_by(
        DeliveryNoteItem.product_id,
        DeliveryNoteItem.lotto
    ).all()
    scarichi_map = {(s.product_id, s.lotto): (s.scarico_kg or 0.0, s.scarico_colli or 0) for s in scarichi}

    suggestions = []
    today = date.today()
    for c in carichi:
        sc_kg, sc_colli = scarichi_map.get((c.product_id, c.lotto), (0.0, 0))
        giacenza_kg = round(float(c.carico_kg or 0.0) - float(sc_kg), 2)
        colli_disp = max(0, int(c.carico_colli or 0) - int(sc_colli))
        if giacenza_kg > 0:
            giorni = (c.data_scadenza - today).days if c.data_scadenza else None
            suggestions.append({
                "product_id": c.product_id,
                "lotto": c.lotto,
                "data_scadenza": c.data_scadenza.isoformat() if c.data_scadenza else None,
                "giorni_a_scadere": giorni,
                "giacenza_kg": giacenza_kg,
                "colli_disponibili": colli_disp
            })

    suggestions.sort(key=lambda x: x['data_scadenza'] or '9999-12-31')
    for idx, item in enumerate(suggestions):
        item['consigliato_fefo'] = (idx == 0)

    return jsonify(suggestions), 200

# ==========================================
# SUPPLY CHAIN: INTERSCAMBIO PALLET (L. 182/2025)
# ==========================================

DEFAULT_PALLET_TYPES = [
    {"codice": "EPAL", "descrizione": "Pallet EUR/EPAL Legno Standard 80x120", "materiale": "legno", "valore_risarcimento": 18.0},
    {"codice": "CPR_40x60", "descrizione": "Cassa CPR System Verde 40x60", "materiale": "plastica", "valore_risarcimento": 2.5},
    {"codice": "CPR_30x40", "descrizione": "Cassa CPR System Verde 30x40", "materiale": "plastica", "valore_risarcimento": 1.8},
    {"codice": "CHEP", "descrizione": "Pallet Blu CHEP 80x120", "materiale": "legno", "valore_risarcimento": 22.0},
    {"codice": "IFCO", "descrizione": "Cassa Pieghevole IFCO Green", "materiale": "plastica", "valore_risarcimento": 3.0}
]

def seed_default_pallet_types():
    if PalletType.query.count() == 0:
        for pt in DEFAULT_PALLET_TYPES:
            db.session.add(PalletType(**pt))
        db.session.commit()

def get_next_pallet_receipt_number(anno):
    max_num = db.session.query(func.max(PalletReceipt.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

@app.route('/api/pallets/types', methods=['GET'])
@require_auth()
def get_pallet_types():
    seed_default_pallet_types()
    types = PalletType.query.filter_by(attivo=True).order_by(PalletType.codice.asc()).all()
    return jsonify([t.to_dict() for t in types]), 200

@app.route('/api/pallets/types', methods=['POST'])
@require_auth(roles=['Admin'])
def create_pallet_type():
    data = request.get_json() or {}
    codice = data.get('codice')
    descrizione = data.get('descrizione')
    if not codice or not descrizione:
        return jsonify({"error": "codice e descrizione sono obbligatori"}), 400
    pt = PalletType(
        codice=codice,
        descrizione=descrizione,
        materiale=data.get('materiale', 'legno'),
        valore_risarcimento=float(data.get('valore_risarcimento', 18.0)),
        attivo=data.get('attivo', True)
    )
    db.session.add(pt)
    db.session.commit()
    return jsonify(pt.to_dict()), 201

@app.route('/api/pallets/receipts', methods=['GET'])
@require_auth()
def get_pallet_receipts():
    query = PalletReceipt.query
    partner_id = request.args.get('partner_id')
    if partner_id:
        query = query.filter_by(partner_id=int(partner_id))
    stato = request.args.get('stato')
    if stato and stato != 'tutti':
        query = query.filter_by(stato=stato)
    search = request.args.get('search')
    if search:
        search_filter = f"%{search}%"
        query = query.join(PalletReceipt.partner).filter(
            (PalletReceipt.numero_completo.ilike(search_filter)) |
            (Partner.ragione_sociale.ilike(search_filter))
        )
    receipts = query.order_by(PalletReceipt.data_emissione.desc(), PalletReceipt.numero.desc()).all()
    return jsonify([r.to_dict() for r in receipts]), 200

@app.route('/api/pallets/receipts/<int:pid>', methods=['GET'])
@require_auth()
def get_pallet_receipt_detail(pid):
    receipt = db.session.get(PalletReceipt, pid)
    if not receipt:
        return jsonify({"error": "Pallet receipt not found"}), 404
    return jsonify(receipt.to_dict()), 200

@app.route('/api/pallets/receipts', methods=['POST'])
@require_auth(roles=['Admin'])
def create_pallet_receipt():
    seed_default_pallet_types()
    data = request.get_json() or {}
    partner_id = data.get('partner_id')
    if not partner_id:
        return jsonify({"error": "partner_id is required"}), 400
    partner = db.session.get(Partner, partner_id)
    if not partner:
        return jsonify({"error": "Partner not found"}), 404

    items_data = data.get('items', [])
    if not items_data:
        return jsonify({"error": "Almeno una tipologia pallet richiesta"}), 400

    doc_date_str = data.get('data_emissione')
    doc_date = datetime.strptime(doc_date_str, '%Y-%m-%d').date() if doc_date_str else date.today()

    term_days = int(data.get('termini_giorni', 60))
    limit_date_str = data.get('data_limite_restituzione')
    limit_date = datetime.strptime(limit_date_str, '%Y-%m-%d').date() if limit_date_str else (doc_date + timedelta(days=term_days))

    anno = doc_date.year
    numero = get_next_pallet_receipt_number(anno)
    numero_completo = f"BP-{anno}-{numero:04d}"

    totale_consegnati = 0
    totale_restituiti = 0
    receipt_items = []

    for it in items_data:
        pt_id = it.get('pallet_type_id')
        ptype = db.session.get(PalletType, pt_id) if pt_id else None
        if not ptype:
            return jsonify({"error": f"PalletType {pt_id} non trovato"}), 404

        q_cons = int(it.get('quantita_consegnata', 0))
        q_rest = int(it.get('quantita_restituita', 0))
        saldo_r = q_cons - q_rest

        totale_consegnati += q_cons
        totale_restituiti += q_rest

        receipt_items.append(PalletReceiptItem(
            pallet_type_id=pt_id,
            quantita_consegnata=q_cons,
            quantita_restituita=q_rest,
            saldo_riga=saldo_r
        ))

    saldo_netto = totale_consegnati - totale_restituiti
    stato = 'saldato' if saldo_netto <= 0 else 'aperto'

    receipt = PalletReceipt(
        numero=numero,
        anno=anno,
        numero_completo=numero_completo,
        data_emissione=doc_date,
        data_limite_restituzione=limit_date,
        partner_id=partner.id,
        delivery_note_id=data.get('delivery_note_id'),
        tipo=data.get('tipo', 'uscita'),
        totale_consegnati=totale_consegnati,
        totale_restituiti=totale_restituiti,
        saldo_netto=saldo_netto,
        stato=stato,
        note=data.get('note'),
        items=receipt_items
    )
    db.session.add(receipt)
    try:
        db.session.commit()
        return jsonify(receipt.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/pallets/receipts/<int:pid>/return', methods=['POST'])
@require_auth(roles=['Admin'])
def return_pallet_receipt(pid):
    receipt = db.session.get(PalletReceipt, pid)
    if not receipt:
        return jsonify({"error": "Pallet receipt not found"}), 404
    if receipt.stato == 'fatturato':
        return jsonify({"error": "Impossibile restituire pallet su un buono già fatturato"}), 400

    data = request.get_json() or {}
    items_returns = data.get('items', [])
    items_map = {it.pallet_type_id: it for it in receipt.items}

    for ret in items_returns:
        pt_id = ret.get('pallet_type_id')
        q_ret = int(ret.get('quantita_restituita', 0))
        item = items_map.get(pt_id)
        if item:
            item.quantita_restituita += q_ret
            item.saldo_riga = item.quantita_consegnata - item.quantita_restituita

    receipt.totale_restituiti = sum(it.quantita_restituita for it in receipt.items)
    receipt.saldo_netto = receipt.totale_consegnati - receipt.totale_restituiti
    if receipt.saldo_netto <= 0:
        receipt.stato = 'saldato'
    else:
        receipt.stato = 'aperto'

    try:
        db.session.commit()
        return jsonify(receipt.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/pallets/ledger', methods=['GET'])
@require_auth()
def get_pallets_ledger():
    seed_default_pallet_types()
    pallet_types = PalletType.query.filter_by(attivo=True).all()
    partners = Partner.query.all()

    ledger = []
    today = date.today()

    for p in partners:
        receipts = PalletReceipt.query.filter_by(partner_id=p.id).all()
        if not receipts:
            continue

        saldi = {pt.codice: 0 for pt in pallet_types}
        buoni_aperti = 0
        buoni_scaduti = 0

        for r in receipts:
            if r.stato == 'aperto':
                buoni_aperti += 1
                if r.data_limite_restituzione and r.data_limite_restituzione < today:
                    buoni_scaduti += 1

                for it in r.items:
                    if it.pallet_type and it.pallet_type.codice in saldi:
                        saldi[it.pallet_type.codice] += it.saldo_riga

        total_debt = sum(saldi.values())
        if total_debt > 0 or buoni_aperti > 0:
            ledger.append({
                "partner_id": p.id,
                "partner_nome": p.ragione_sociale,
                "partner_tipo": p.tipo,
                "saldi": saldi,
                "totale_bancali_debito": total_debt,
                "buoni_aperti_count": buoni_aperti,
                "buoni_scaduti_count": buoni_scaduti
            })

    ledger.sort(key=lambda x: x['totale_bancali_debito'], reverse=True)
    return jsonify(ledger), 200

@app.route('/api/pallets/receipts/<int:pid>/invoice-unreturned', methods=['POST'])
@require_auth(roles=['Admin'])
def invoice_unreturned_pallets(pid):
    receipt = db.session.get(PalletReceipt, pid)
    if not receipt:
        return jsonify({"error": "Pallet receipt not found"}), 404
    if receipt.stato == 'saldato':
        return jsonify({"error": "Il buono pallet è già saldato"}), 400
    if receipt.stato == 'fatturato':
        return jsonify({"error": "Il buono pallet è già stato fatturato"}), 400

    items_unreturned = [it for it in receipt.items if it.saldo_riga > 0]
    if not items_unreturned:
        return jsonify({"error": "Nessun pallet a debito da fatturare"}), 400

    today = date.today()
    anno = today.year
    numero = get_next_invoice_number(anno)
    numero_completo = f"FT-{anno}-{numero:04d}"

    totale_imponibile = 0.0
    invoice_items = []

    for it in items_unreturned:
        valore = float(it.pallet_type.valore_risarcimento if it.pallet_type else 18.0)
        qta = float(it.saldo_riga)
        imp_riga = round(qta * valore, 2)
        totale_imponibile += imp_riga

        prod = Product.query.filter_by(codice=f"IMB-{it.pallet_type.codice}").first()
        if not prod:
            prod = Product.query.filter_by(categoria="imballo").first()
        prod_id = prod.id if prod else 1

        invoice_items.append(InvoiceItem(
            product_id=prod_id,
            descrizione=f"Cessione {it.pallet_type.descrizione} non restituiti ex L. 182/2025 da Buono {receipt.numero_completo}",
            unita_misura="PZ",
            colli=int(qta),
            quantita=qta,
            prezzo_unitario=valore,
            aliquota_iva=0,
            imponibile_riga=imp_riga
        ))

    totale_imponibile = round(totale_imponibile, 2)
    totale_fattura = totale_imponibile

    note_fiscale = (
        f"Fatturazione mancata restituzione pallet ex L. 182/2025 su Buono Pallet {receipt.numero_completo}. "
        "Operazione in Reverse Charge ai sensi dell'Art. 74 comma 7/8 DPR 633/72 per cessione imballaggi usati."
    )

    rate_data = calculate_installments(totale_fattura, today, receipt.partner.condizioni_pagamento or '30gg fm')
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
        tipo_documento='TD01',
        data_documento=today,
        cliente_id=receipt.partner_id,
        condizioni_pagamento=receipt.partner.condizioni_pagamento or '30gg fm',
        esigibilita_iva='I',
        totale_imponibile=totale_imponibile,
        totale_imposta=0.0,
        totale_fattura=totale_fattura,
        castelletto_iva={"0": {"imponibile": totale_imponibile, "imposta": 0.0}},
        stato='emessa',
        note=note_fiscale,
        items=invoice_items,
        installments=installments
    )
    db.session.add(invoice)

    receipt.stato = 'fatturato'

    try:
        db.session.commit()
        return jsonify(invoice.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

# ==========================================
# SUPPLY CHAIN: SPEDIZIONI INTERNAZIONALI & CMR (EXPORT)
# ==========================================

def get_next_cmr_number(anno):
    max_num = db.session.query(func.max(CmrDocument.numero)).filter_by(anno=anno).scalar()
    return (max_num or 0) + 1

@app.route('/api/cmr', methods=['GET'])
@require_auth()
def get_cmr_documents():
    query = CmrDocument.query
    cliente_id = request.args.get('cliente_id')
    if cliente_id:
        query = query.filter_by(cliente_id=int(cliente_id))
    vettore_id = request.args.get('vettore_id')
    if vettore_id:
        query = query.filter_by(vettore_id=int(vettore_id))
    anno = request.args.get('anno')
    if anno:
        query = query.filter_by(anno=int(anno))
    search = request.args.get('search')
    if search:
        search_filter = f"%{search}%"
        query = query.join(CmrDocument.cliente).filter(
            (CmrDocument.numero_completo.ilike(search_filter)) |
            (Partner.ragione_sociale.ilike(search_filter)) |
            (CmrDocument.luogo_consegna.ilike(search_filter))
        )
    documents = query.order_by(CmrDocument.data_documento.desc(), CmrDocument.numero.desc()).all()
    return jsonify([d.to_dict() for d in documents]), 200

@app.route('/api/cmr/<int:cid>', methods=['GET'])
@require_auth()
def get_cmr_detail(cid):
    cmr = db.session.get(CmrDocument, cid)
    if not cmr:
        return jsonify({"error": "CMR not found"}), 404
    return jsonify(cmr.to_dict()), 200

@app.route('/api/cmr/from-ddt/<int:ddt_id>', methods=['POST'])
@require_auth(roles=['Admin'])
def create_cmr_from_ddt(ddt_id):
    ddt = db.session.get(DeliveryNote, ddt_id)
    if not ddt:
        return jsonify({"error": "DDT not found"}), 404
    if not ddt.cliente:
        return jsonify({"error": "DDT privo di cliente associato"}), 400

    today = date.today()
    anno = today.year
    numero = get_next_cmr_number(anno)
    numero_completo = f"CMR-{anno}-{numero:04d}"

    vettore_nome = (ddt.vettore.ragione_sociale if ddt.vettore else "").upper()
    if "LD TRASPORTI" in vettore_nome:
        luogo_carico = "ALESSANDRIA (AL)"
    else:
        luogo_carico = "SEDE MITTENTE (BOLOGNA)"

    luogo_consegna_parts = [
        ddt.cliente.indirizzo or "",
        ddt.cliente.citta or "",
        f"({ddt.cliente.nazione})" if ddt.cliente.nazione else ""
    ]
    luogo_consegna = ", ".join([p for p in luogo_consegna_parts if p]) or "DESTINAZIONE CLIENTE"

    cmr_items = []
    totale_colli = 0
    peso_totale_netto = 0.0
    peso_totale_lordo = 0.0

    for idx, d_item in enumerate(ddt.items):
        colli = d_item.colli or 1
        p_netto = float(d_item.quantita or 0.0)
        p_lordo = round(p_netto * 1.05, 2)

        totale_colli += colli
        peso_totale_netto += p_netto
        peso_totale_lordo += p_lordo

        codice_nc = d_item.product.codice_nc if (d_item.product and hasattr(d_item.product, 'codice_nc')) else None

        cmr_items.append(CmrItem(
            riga_numero=idx + 1,
            contrassegno_lotto=d_item.lotto,
            numero_colli=colli,
            modo_imballaggio="Casse su Pallet",
            natura_merce=d_item.descrizione,
            codice_nc=codice_nc,
            peso_netto_kg=p_netto,
            peso_lordo_kg=p_lordo
        ))

    ha_allegato_righe = len(cmr_items) > 21

    cmr = CmrDocument(
        numero=numero,
        anno=anno,
        numero_completo=numero_completo,
        data_documento=today,
        delivery_note_id=ddt.id,
        cliente_id=ddt.cliente_id,
        vettore_id=ddt.vettore_id,
        luogo_carico=luogo_carico,
        luogo_consegna=luogo_consegna,
        targa_automezzo=None,
        targa_rimorchio=None,
        istruzioni_mittente="Merci biologiche destinate all'export comunitario. Origine preferenziale CE.",
        totale_colli=totale_colli,
        peso_totale_netto=round(peso_totale_netto, 2),
        peso_totale_lordo=round(peso_totale_lordo, 2),
        ha_allegato_righe=ha_allegato_righe,
        stato="emesso",
        items=cmr_items
    )
    db.session.add(cmr)
    try:
        db.session.commit()
        return jsonify(cmr.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/cmr', methods=['POST'])
@require_auth(roles=['Admin'])
def create_cmr_manual():
    data = request.get_json() or {}
    cliente_id = data.get('cliente_id')
    if not cliente_id:
        return jsonify({"error": "cliente_id obbligatorio"}), 400
    cliente = db.session.get(Partner, cliente_id)
    if not cliente:
        return jsonify({"error": "Cliente non trovato"}), 404

    items_data = data.get('items', [])
    if not items_data:
        return jsonify({"error": "Almeno una riga merce richiesta"}), 400

    today = date.today()
    anno = today.year
    numero = get_next_cmr_number(anno)
    numero_completo = f"CMR-{anno}-{numero:04d}"

    vettore_id = data.get('vettore_id')
    vettore = db.session.get(Partner, vettore_id) if vettore_id else None
    vettore_nome = (vettore.ragione_sociale if vettore else "").upper()

    default_hub = "ALESSANDRIA (AL)" if "LD TRASPORTI" in vettore_nome else "SEDE MITTENTE"
    luogo_carico = data.get('luogo_carico') or default_hub

    totale_colli = 0
    peso_totale_netto = 0.0
    peso_totale_lordo = 0.0
    cmr_items = []

    for idx, it in enumerate(items_data):
        colli = int(it.get('numero_colli', 1))
        p_netto = float(it.get('peso_netto_kg', 0.0))
        p_lordo = float(it.get('peso_lordo_kg', p_netto * 1.05))

        totale_colli += colli
        peso_totale_netto += p_netto
        peso_totale_lordo += p_lordo

        cmr_items.append(CmrItem(
            riga_numero=idx + 1,
            contrassegno_lotto=it.get('contrassegno_lotto'),
            numero_colli=colli,
            modo_imballaggio=it.get('modo_imballaggio', 'Casse su Pallet'),
            natura_merce=it.get('natura_merce', 'Ortofrutta Bio'),
            codice_nc=it.get('codice_nc'),
            peso_netto_kg=round(p_netto, 2),
            peso_lordo_kg=round(p_lordo, 2)
        ))

    ha_allegato_righe = len(cmr_items) > 21

    cmr = CmrDocument(
        numero=numero,
        anno=anno,
        numero_completo=numero_completo,
        data_documento=today,
        delivery_note_id=data.get('delivery_note_id'),
        cliente_id=cliente.id,
        vettore_id=vettore_id,
        luogo_carico=luogo_carico,
        luogo_consegna=data.get('luogo_consegna') or f"{cliente.citta} ({cliente.nazione})",
        targa_automezzo=data.get('targa_automezzo'),
        targa_rimorchio=data.get('targa_rimorchio'),
        istruzioni_mittente=data.get('istruzioni_mittente', "Merci da agricoltura biologica. Origine preferenziale CE."),
        totale_colli=totale_colli,
        peso_totale_netto=round(peso_totale_netto, 2),
        peso_totale_lordo=round(peso_totale_lordo, 2),
        ha_allegato_righe=ha_allegato_righe,
        stato="emesso",
        items=cmr_items
    )
    db.session.add(cmr)
    try:
        db.session.commit()
        return jsonify(cmr.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/cmr/<int:cid>', methods=['PUT'])
@require_auth(roles=['Admin'])
def update_cmr(cid):
    cmr = db.session.get(CmrDocument, cid)
    if not cmr:
        return jsonify({"error": "CMR not found"}), 404
    data = request.get_json() or {}
    if 'targa_automezzo' in data:
        cmr.targa_automezzo = data['targa_automezzo']
    if 'targa_rimorchio' in data:
        cmr.targa_rimorchio = data['targa_rimorchio']
    if 'luogo_carico' in data:
        cmr.luogo_carico = data['luogo_carico']
    if 'luogo_consegna' in data:
        cmr.luogo_consegna = data['luogo_consegna']
    if 'istruzioni_mittente' in data:
        cmr.istruzioni_mittente = data['istruzioni_mittente']
    try:
        db.session.commit()
        return jsonify(cmr.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route('/api/cmr/<int:cid>/print', methods=['GET'])
@require_auth()
def get_cmr_print_format(cid):
    cmr = db.session.get(CmrDocument, cid)
    if not cmr:
        return jsonify({"error": "CMR not found"}), 404

    boxes = {
        "numero_cmr": cmr.numero_completo,
        "data_emissione": cmr.data_documento.isoformat(),
        "casella_1_mittente": {
            "ragione_sociale": "ReteBio Società Cooperativa Agricola",
            "indirizzo": "Via della Cooperazione 12",
            "citta": "Bologna",
            "cap": "40100",
            "nazione": "IT",
            "piva": "IT01234567890"
        },
        "casella_2_destinatario": cmr.cliente.to_dict() if cmr.cliente else {},
        "casella_3_luogo_consegna": cmr.luogo_consegna,
        "casella_4_luogo_carico": {
            "luogo": cmr.luogo_carico,
            "data": cmr.data_documento.isoformat()
        },
        "casella_6_a_12_merci": [it.to_dict() for it in cmr.items] if not cmr.ha_allegato_righe else [{"dicitura": "--- VEDI ELENCO MERCE IN ALLEGATO ---"}],
        "caselle_merci": [it.to_dict() for it in cmr.items],
        "casella_13_istruzioni_mittente": cmr.istruzioni_mittente,
        "casella_16_trasportatore": {
            "ragione_sociale": cmr.vettore.ragione_sociale if cmr.vettore else "Vettore Incaricato",
            "indirizzo": cmr.vettore.indirizzo if cmr.vettore else "",
            "citta": cmr.vettore.citta if cmr.vettore else "",
            "targa_automezzo": cmr.targa_automezzo,
            "targa_rimorchio": cmr.targa_rimorchio
        },
        "totale_colli": cmr.totale_colli,
        "peso_totale_netto": cmr.peso_totale_netto,
        "peso_totale_lordo": cmr.peso_totale_lordo,
        "ha_allegato_righe": cmr.ha_allegato_righe
    }
    return jsonify(boxes), 200

# ==========================================
# EVENT BUS, AUDIT TRAIL & BACKGROUND TASKS
# ==========================================

@app.route('/api/events/channels', methods=['GET'])
@require_auth()
def get_event_channels():
    seed_default_channels_and_categories()
    channels = EventChannel.query.filter_by(attivo=True).order_by(EventChannel.codice.asc()).all()
    return jsonify([c.to_dict() for c in channels]), 200

@app.route('/api/events/channels', methods=['POST'])
@require_auth(roles=['Admin'])
def create_event_channel():
    data = request.get_json() or {}
    codice = (data.get('codice') or '').strip().upper()
    nome = (data.get('nome') or '').strip()
    if not codice or not nome:
        return jsonify({"error": "codice e nome obbligatori"}), 400
    ch = EventChannel(
        codice=codice,
        nome=nome,
        descrizione=data.get('descrizione'),
        tipo_dispatcher=data.get('tipo_dispatcher', 'internal'),
        configurazione=data.get('configurazione'),
        richiede_destinatario=data.get('richiede_destinatario', False),
        attivo=data.get('attivo', True)
    )
    db.session.add(ch)
    db.session.commit()
    return jsonify(ch.to_dict()), 201

@app.route('/api/events/categories', methods=['GET'])
@require_auth()
def get_event_categories():
    seed_default_channels_and_categories()
    categories = EventCategory.query.filter_by(attivo=True).order_by(EventCategory.codice.asc()).all()
    return jsonify([cat.to_dict() for cat in categories]), 200

@app.route('/api/events/types', methods=['GET'])
@require_auth()
def get_event_types():
    seed_default_channels_and_categories()
    types = EventType.query.order_by(EventType.codice.asc()).all()
    return jsonify([t.to_dict() for t in types]), 200

@app.route('/api/events/types', methods=['POST'])
@require_auth(roles=['Admin'])
def create_event_type():
    data = request.get_json() or {}
    codice = (data.get('codice') or '').strip().upper()
    nome = (data.get('nome') or '').strip()
    channel_id = data.get('channel_id')
    if not codice or not nome or not channel_id:
        return jsonify({"error": "codice, nome e channel_id sono obbligatori"}), 400
    et = EventType(
        codice=codice,
        nome=nome,
        descrizione=data.get('descrizione'),
        channel_id=channel_id,
        category_id=data.get('category_id'),
        modalita_esecuzione=data.get('modalita_esecuzione', 'sincrono'),
        coda_nome=data.get('coda_nome', 'default'),
        livello_default=data.get('livello_default', 'info'),
        attivo=data.get('attivo', True)
    )
    db.session.add(et)
    db.session.commit()
    return jsonify(et.to_dict()), 201

@app.route('/api/events/types/<int:tid>', methods=['PUT'])
@require_auth(roles=['Admin'])
def update_event_type_policy(tid):
    et = db.session.get(EventType, tid)
    if not et:
        return jsonify({"error": "Tipo evento non trovato"}), 404
    data = request.get_json() or {}
    if 'modalita_esecuzione' in data:
        et.modalita_esecuzione = data['modalita_esecuzione']
    if 'coda_nome' in data:
        et.coda_nome = data['coda_nome']
    if 'channel_id' in data:
        et.channel_id = data['channel_id']
    if 'category_id' in data:
        et.category_id = data['category_id']
    if 'attivo' in data:
        et.attivo = data['attivo']
    db.session.commit()
    return jsonify(et.to_dict()), 200

@app.route('/api/events/queues', methods=['GET'])
@require_auth()
def get_redis_queues_stats():
    queue_names = ['critical', 'emails', 'batch', 'default']
    queues_stats = []
    redis_conn = get_redis_connection()
    from rq import Queue

    for q_name in queue_names:
        job_count = 0
        if redis_conn:
            try:
                q = Queue(q_name, connection=redis_conn)
                job_count = len(q)
            except Exception:
                pass
        queues_stats.append({
            "name": q_name,
            "count": job_count,
            "active": redis_conn is not None
        })
    return jsonify({"queues": queues_stats}), 200

@app.route('/api/events', methods=['GET'])
@require_auth()
def get_events():
    seed_default_channels_and_categories()
    query = SystemEvent.query
    channel_codice = request.args.get('channel')
    if channel_codice and channel_codice != 'tutti':
        query = query.join(SystemEvent.channel).filter(EventChannel.codice == channel_codice)
    stato = request.args.get('stato')
    if stato and stato != 'tutti':
        query = query.filter(SystemEvent.stato == stato)
    search = request.args.get('search')
    if search:
        search_f = f"%{search}%"
        query = query.filter((SystemEvent.titolo.ilike(search_f)) | (SystemEvent.azione.ilike(search_f)) | (SystemEvent.descrizione.ilike(search_f)))
    is_async = request.args.get('is_async')
    if is_async is not None:
        query = query.filter(SystemEvent.is_async == (is_async.lower() == 'true'))

    events = query.order_by(SystemEvent.data_creazione.desc()).limit(100).all()
    return jsonify([ev.to_dict() for ev in events]), 200

@app.route('/api/events/<int:eid>', methods=['GET'])
@require_auth()
def get_event_detail(eid):
    ev = db.session.get(SystemEvent, eid)
    if not ev:
        return jsonify({"error": "Evento non trovato"}), 404
    return jsonify(ev.to_dict()), 200

@app.route('/api/events', methods=['POST'])
@require_auth()
def create_event_endpoint():
    data = request.get_json() or {}
    is_async = data.get('is_async', False)
    ev = dispatch_event(
        channel_code=data.get('channel_code', 'AUDIT'),
        category_code=data.get('category_code', 'SISTEMA'),
        azione=data.get('azione', 'custom_event'),
        titolo=data.get('titolo', 'Evento Utente'),
        descrizione=data.get('descrizione'),
        payload_dati=data.get('payload_dati'),
        destinatario_recapito=data.get('destinatario_recapito'),
        partner_id=data.get('partner_id'),
        entita_tipo=data.get('entita_tipo'),
        entita_id=data.get('entita_id'),
        is_async=is_async,
        livello=data.get('livello', 'info')
    )
    code = 202 if is_async else 201
    return jsonify(ev.to_dict()), code

@app.route('/api/events/<int:eid>/retry', methods=['POST'])
@require_auth(roles=['Admin'])
def retry_event(eid):
    ev = db.session.get(SystemEvent, eid)
    if not ev:
        return jsonify({"error": "Evento non trovato"}), 404
    ev.stato = 'in_coda'
    ev.progresso = 0
    ev.tentativi += 1
    db.session.commit()
    from flask import current_app
    app_obj = current_app._get_current_object()
    from services.event_dispatcher import executor, _run_async_event
    if app_obj.config.get("TESTING"):
        _run_async_event(app_obj, ev.id)
    else:
        executor.submit(_run_async_event, app_obj, ev.id)
    return jsonify(ev.to_dict()), 202

@app.route('/api/pallets/batch-solleciti', methods=['POST'])
@require_auth(roles=['Admin'])
def batch_solleciti_pallets():
    today = date.today()
    expired_receipts = PalletReceipt.query.filter(
        PalletReceipt.stato == 'aperto',
        PalletReceipt.data_limite_restituzione < today
    ).all()

    desc = f"Avvio solleciti massivi per {len(expired_receipts)} buoni pallet scaduti oltre i termini di legge."

    def _process_solleciti(event):
        totale = len(expired_receipts)
        for i, r in enumerate(expired_receipts):
            time.sleep(0.02)
            event.progresso = int(((i + 1) / max(1, totale)) * 100)
            db.session.commit()

    ev = dispatch_event(
        channel_code="EMAIL",
        category_code="PALLET",
        azione="sollecito_massivo_pallet",
        titolo="Sollecito Massivo Buoni Pallet Scaduti",
        descrizione=desc,
        payload_dati={"conteggio_scaduti": len(expired_receipts)},
        is_async=True,
        target_func=_process_solleciti
    )
    return jsonify(ev.to_dict()), 202
    
@socketio.on('connect')
def handle_connect():
    print("Client connesso!")

if __name__ == '__main__':
    # Flask runs on port 5000 by default
    socketio.run(app, host='0.0.0.0', port=5000)