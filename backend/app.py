from gevent import monkey
monkey.patch_all()

from flask import Flask, jsonify, request, Response
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, create_access_token
from flask_cors import CORS # Needed for the frontend to talk to the backend
import os
import io
import csv
from models import db, User, Partner, Product, DeliveryNote, DeliveryNoteItem, Invoice, InvoiceItem, InvoiceInstallment, Account, JournalEntry, JournalItem
from sqlalchemy import text
from sqlalchemy import inspect, func
from datetime import datetime, date, timedelta
import calendar
import re
from functools import wraps
from flask_socketio import SocketIO, emit

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

@app.route('/api/invoices/<int:iid>', methods=['GET'])
@require_auth()
def get_invoice_detail(iid):
    invoice = db.session.get(Invoice, iid)
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    return jsonify(invoice.to_dict()), 200

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
    
@socketio.on('connect')
def handle_connect():
    print("Client connesso!")

if __name__ == '__main__':
    # Flask runs on port 5000 by default
    socketio.run(app, host='0.0.0.0', port=5000)