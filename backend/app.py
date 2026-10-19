from gevent import monkey
monkey.patch_all()

from flask import Flask, jsonify, request
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, create_access_token
from flask_cors import CORS # Needed for the frontend to talk to the backend
import os
from models import db, User
from sqlalchemy import text
from sqlalchemy import inspect, func
from datetime import datetime
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
    
@socketio.on('connect')
def handle_connect():
    print("Client connesso!")

if __name__ == '__main__':
    # Flask runs on port 5000 by default
    socketio.run(app, host='0.0.0.0', port=5000)