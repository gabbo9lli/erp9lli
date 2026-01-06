from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token
from flask_cors import CORS # Needed for the frontend to talk to the backend

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "super-secret-key" # Change this!
jwt = JWTManager(app)
# Allow all origins for simplicity in development
CORS(app)
# CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})

# Mock database
users = {"pippo@1.com": "pippo", }

@app.route('/api/data')
def get_data():
    return {"message": "Hello from Flask!"}

@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify({"message": "Hello from the Flask backend!", "status": "success"})

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if email in users:
        return jsonify({"msg": "User already exists"}), 400
    users[email] = password
    return jsonify({"msg": "User created successfully"}), 201

@app.route('/api/signin', methods=['POST'])
def signin():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if users.get(email) == password:
        token = create_access_token(identity=email)
        return jsonify(access_token=token), 200
    return jsonify({"msg": "Bad email or password"}), 401

if __name__ == '__main__':
    # Flask runs on port 5000 by default
    app.run(host='0.0.0.0', port=5000)