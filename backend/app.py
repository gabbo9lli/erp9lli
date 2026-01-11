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

app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["JWT_SECRET_KEY"] = "super-secret-key" # Change this!
jwt = JWTManager(app)
CORS(app)

DB_TYPE = os.environ.get('DB_TYPE', 'sqlite')
if DB_TYPE == 'postgres':
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

db.init_app(app)
migrate = Migrate(app, db)

# Mock database
users = {"pippo@1.com": "pippo", }

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
    
    user = User(email=email)
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "Account created successfully"}), 201

@app.route('/api/signin', methods=['POST'])
def signin():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if users.get(email) == password:
        token = create_access_token(identity=email)
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

@app.route('/api/users', methods=['GET', 'POST'])
def handle_users():
    if request.method == 'POST':
        data = request.json
        new_user = User(email=data['email'])
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User created!"}), 201
    
    users = User.query.all()
    return jsonify([{"email": u.email} for u in users])

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
def get_table_data(table_name):
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

if __name__ == '__main__':
    # Flask runs on port 5000 by default
    app.run(host='0.0.0.0', port=5000)