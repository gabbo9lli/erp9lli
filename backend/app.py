from flask import Flask, jsonify
from flask_cors import CORS # Needed for the frontend to talk to the backend

app = Flask(__name__)
# Allow all origins for simplicity in development
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})

@app.route('/api/data')
def get_data():
    return {"message": "Hello from Flask!"}

@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify({"message": "Hello from the Flask backend!", "status": "success"})

if __name__ == '__main__':
    # Flask runs on port 5000 by default
    app.run(host='0.0.0.0', port=5000)