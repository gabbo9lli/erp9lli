import pytest
from models import User

def test_health_check(client, db_session):
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data['flask_status'] == 'UP'
    assert data['database']['status'] == 'UP'

def test_signup_and_signin_jwt(client, db_session):
    # Signup
    signup_res = client.post('/api/signup', json={
        'email': 'developer@example.com',
        'password': 'SecurePassword123!'
    })
    assert signup_res.status_code == 201
    assert signup_res.get_json()['message'] == 'Account created successfully'

    # Signin (JWT token)
    signin_res = client.post('/api/signin', json={
        'email': 'developer@example.com',
        'password': 'SecurePassword123!'
    })
    assert signin_res.status_code == 200
    data = signin_res.get_json()
    assert 'access_token' in data
    assert len(data['access_token']) > 10

def test_signin_invalid_credentials(client, db_session):
    res = client.post('/api/signin', json={
        'email': 'nonexistent@example.com',
        'password': 'WrongPassword!'
    })
    assert res.status_code == 401
    assert 'msg' in res.get_json()

def test_login_endpoint(client, db_session):
    client.post('/api/signup', json={
        'email': 'loginuser@example.com',
        'password': 'Password123!'
    })
    res = client.post('/api/login', json={
        'email': 'loginuser@example.com',
        'password': 'Password123!'
    })
    assert res.status_code == 200
    assert res.get_json()['user'] == 'loginuser@example.com'

def test_db_explorer_tables(client, db_session):
    admin_headers = {
        'X-Forwarded-Email': 'admin@example.com',
        'X-Forwarded-Groups': 'admin'
    }
    client.get('/api/me', headers=admin_headers)
    res = client.get('/api/db-explorer', headers=admin_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert 'tables' in data
    table_names = [t['name'] for t in data['tables']]
    assert 'user' in table_names

def test_db_explorer_sqli_protection(client, db_session):
    admin_headers = {
        'X-Forwarded-Email': 'admin@example.com',
        'X-Forwarded-Groups': 'admin'
    }
    client.get('/api/me', headers=admin_headers)
    # Invalid table should return 404
    res = client.get('/api/db-explorer/fake_table_not_exists/data', headers=admin_headers)
    assert res.status_code == 404
    assert res.get_json()['error'] == 'Table not found'

    # Injection string should be safely rejected with 404
    sqli_res = client.get('/api/db-explorer/user;DROP%20TABLE%20user;/data', headers=admin_headers)
    assert sqli_res.status_code == 404

def test_password_reset_flow(client, db_session):
    client.post('/api/signup', json={
        'email': 'resetuser@example.com',
        'password': 'InitialPassword123!'
    })

    # Forgot password
    forgot_res = client.post('/api/forgot-password', json={
        'email': 'resetuser@example.com'
    })
    assert forgot_res.status_code == 200

    # Retrieve reset token
    user = db_session.query(User).filter_by(email='resetuser@example.com').first()
    token = user.reset_token
    assert token is not None

    # Reset password with token
    reset_res = client.post('/api/reset-password', json={
        'token': token,
        'new_password': 'UpdatedPassword123!'
    })
    assert reset_res.status_code == 200

    # Verify login with new password
    login_new = client.post('/api/login', json={
        'email': 'resetuser@example.com',
        'password': 'UpdatedPassword123!'
    })
    assert login_new.status_code == 200

    # Verify old password no longer works
    login_old = client.post('/api/login', json={
        'email': 'resetuser@example.com',
        'password': 'InitialPassword123!'
    })
    assert login_old.status_code == 401

def test_websocket_connection(client, db_session):
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text("ping")
        data = websocket.receive_text()
        assert data == "pong"
