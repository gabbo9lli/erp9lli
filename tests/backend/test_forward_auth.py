import pytest
import os
from models import User

def test_api_me_unauthenticated_production(client, db_session):
    # In non-development mode or when headers are missing
    res = client.get('/api/me')
    assert res.status_code == 401
    assert res.json()['authenticated'] is False

def test_api_me_auto_provisioning_standard_user(client, db_session):
    headers = {
        'X-Forwarded-Email': 'alice@company.com',
        'X-Forwarded-Preferred-Username': 'alice'
    }
    res = client.get('/api/me', headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data['authenticated'] is True
    assert data['email'] == 'alice@company.com'
    assert data['username'] == 'alice'
    assert data['role'] == 'User'

    # Verify user exists in DB
    user = db_session.query(User).filter_by(email='alice@company.com').first()
    assert user is not None
    assert user.role == 'User'
    assert user.password_hash is None

def test_api_me_role_mapping_admin(client, db_session):
    headers = {
        'X-Forwarded-Email': 'bob@company.com',
        'X-Forwarded-Preferred-Username': 'bob',
        'X-Forwarded-Groups': 'erp-admins,staff'
    }
    res = client.get('/api/me', headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data['authenticated'] is True
    assert data['role'] == 'Admin'

def test_api_me_existing_user_no_duplicate(client, db_session):
    # First call provisions user
    headers = {
        'X-Forwarded-Email': 'carol@company.com',
        'X-Forwarded-Preferred-Username': 'carol'
    }
    client.get('/api/me', headers=headers)

    # Second call returns existing
    res = client.get('/api/me', headers=headers)
    assert res.status_code == 200
    assert res.json()['email'] == 'carol@company.com'

    count = db_session.query(User).filter_by(email='carol@company.com').count()
    assert count == 1

def test_require_auth_rbac(client, db_session):
    # Setup users
    admin_headers = {
        'X-Forwarded-Email': 'superadmin@company.com',
        'X-Forwarded-Preferred-Username': 'superadmin',
        'X-Forwarded-Groups': 'admin'
    }
    client.get('/api/me', headers=admin_headers)

    user_headers = {
        'X-Forwarded-Email': 'regularuser@company.com',
        'X-Forwarded-Preferred-Username': 'regularuser'
    }
    client.get('/api/me', headers=user_headers)

    # Accessing DB explorer without auth header -> 401
    res_anon = client.get('/api/db-explorer')
    assert res_anon.status_code == 401

    # Accessing DB explorer with regular user -> 403
    res_user = client.get('/api/db-explorer', headers=user_headers)
    assert res_user.status_code == 403

    # Accessing DB explorer with admin -> 200
    res_admin = client.get('/api/db-explorer', headers=admin_headers)
    assert res_admin.status_code == 200
