# Consolidamento Progetto erp9lli - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidare il progetto erp9lli risolvendo i bug bloccanti a runtime (backend e frontend), sanificando le vulnerabilità di sicurezza (SQL Injection e segreti), armonizzando la configurazione multi-ambiente Docker (porte Gunicorn/Nginx, DB_TYPE), aggiungendo una suite di test automatizzati con pytest e finalizzando le modifiche con un commit GPG firmato.

**Architecture:** Architettura a microservizi containerizzati (Flask API backend con SQLAlchemy e SocketIO, Vue 3 SPA frontend con Quasar e Vite, Nginx reverse proxy con supporto WebSocket, PostgreSQL e Redis). Il consolidamento garantisce la compatibilità trasparente tra sviluppo locale e produzione containerizzata.

**Tech Stack:** Python 3.11, Flask 2.3.3, Flask-SQLAlchemy, Flask-Migrate, Flask-JWT-Extended, Flask-SocketIO, gevent, PostgreSQL 15, Redis, Vue 3, Vite, Quasar 2.16, Nginx Alpine, Docker Compose, Pytest.

**Spec:** Risultati dell'audit tecnico e piano di consolidamento concordato con l'utente.

## Global Constraints

- **Git & GPG Signing:** L'agente DEVE firmare il commit con `git -c user.signingkey=A62BFD763FD350B1 commit -S -m "..."`.
- **Nessuna regressione su Docker Dev/Prod:** I comandi di avvio `docker compose` per Dev e Prod devono funzionare senza modifiche ai comandi originali.
- **Isolamento e sicurezza:** Rimozione SQL injection e sanitizzazione input su DB explorer.

## Review Focus

1. **Port Mismatch in Produzione:** Gunicorn in `entrypoint.sh` deve essere su porta `8000` in produzione per rispondere a Nginx `proxy_pass http://backend:8000;`.
2. **Compatibilità DB_TYPE:** Sia `postgres` che `postgresql` devono essere gestiti correttamente in `app.py` e `entrypoint.sh`.
3. **Endpoint `/api/signin`:** Deve autenticare l'utente via DB e restituire un access token JWT senza sollevare `NameError`.
4. **Router nel Frontend:** `Auth.vue` non deve crashare dopo il login con `ReferenceError: router is not defined`.
5. **SQL Injection in DB Explorer:** `/api/db-explorer/<table_name>/data` deve rifiutare nomi di tabella non presenti nello schema.

---

### Task 1: Backend Fixes - Configurazione, DB_TYPE, Gunicorn Port e Seed

**Files:**
- Modify: `backend/entrypoint.sh`
- Modify: `backend/app.py:30-50`
- Modify: `backend/seed.py`
- Modify: `.env.dev`
- Modify: `.env.prod`

**Interfaces:**
- Consumes: Variabili d'ambiente `DB_TYPE`, `DATABASE_URL`, `FLASK_ENV`.
- Produces: Connessione corretta a PostgreSQL, bind su porta 8000 per Gunicorn in produzione, script `seed.py` valido.

- [ ] **Step 1: Aggiornare `backend/entrypoint.sh`**
  - Rendere il controllo `DB_TYPE` tollerante sia a `postgres` che a `postgresql`: `if [ "$DB_TYPE" = "postgres" ] || [ "$DB_TYPE" = "postgresql" ]; then`.
  - In modalità produzione (`$FLASK_ENV = "production"`), impostare il bind di Gunicorn su `0.0.0.0:8000` per allinearlo a Nginx (`proxy_pass http://backend:8000;`).

- [ ] **Step 2: Aggiornare `backend/app.py` per DB_TYPE e JWT Secret**
  - Impostare `DB_TYPE in ('postgres', 'postgresql')` per la configurazione di `SQLALCHEMY_DATABASE_URI`.
  - Leggere `JWT_SECRET_KEY` da `os.environ.get('JWT_SECRET_KEY', 'dev-secret-key-change-in-prod')`.

- [ ] **Step 3: Correggere `.env.dev` e `.env.prod`**
  - In `.env.dev`: confermare `DB_TYPE=postgres`.
  - In `.env.prod`: aggiungere `DB_TYPE=postgres`.

- [ ] **Step 4: Correggere `backend/seed.py`**
  - Creare l'utente di test fornendo sia `email='dev@example.com'` che `username='dev@example.com'` (e password iniziale con `set_password`), rispettando il vincolo `nullable=False`.

- [ ] **Step 5: Verificare la sintassi Python di `backend/app.py` e `backend/seed.py`**
  - Run: `python3 -m py_compile backend/app.py backend/seed.py`
  - Expected: Esito pulito (exit code 0).

---

### Task 2: Backend Security & API Fixes - `/api/signin`, SQLi Explorer e Real-time

**Files:**
- Modify: `backend/app.py:65-95`
- Modify: `backend/app.py:120-135`
- Modify: `backend/app.py:210-245`

**Interfaces:**
- Consumes: Richieste POST su `/api/signin`, GET su `/api/db-explorer/<table_name>/data`.
- Produces: Token JWT valido su credenziali corrette, errore 401 su credenziali errate; query protette con whitelist su DB Explorer; evento WebSocket `users_update`.

- [ ] **Step 1: Correggere `/api/signin` in `backend/app.py`**
  - Rimuovere il riferimento al dizionario inesistente `users`.
  - Cercare l'utente nel database: `user = User.query.filter_by(email=email).first()`.
  - Verificare la password con `user.check_password(password)`.
  - Se valido, restituire `jsonify(access_token=create_access_token(identity=user.email)), 200`.
  - Se errato o utente non trovato, restituire `jsonify({"msg": "Bad email or password"}), 401`.

- [ ] **Step 2: Bonificare SQL Injection in `/api/db-explorer/<table_name>/data`**
  - Recuperare la lista delle tabelle consentite tramite `inspector.get_table_names()`.
  - Se `table_name` non è presente nell'elenco delle tabelle consentite, restituire `jsonify({"error": "Table not found"}), 404`.
  - Eseguire la query solo dopo aver validato il nome tabella.

- [ ] **Step 3: Armonizzare eventi Socket.IO**
  - Assicurarsi che `emit('users_update', data, broadcast=True)` venga emesso sia su richiesta che a seguito di variazioni anagrafiche in `user_service`.

- [ ] **Step 4: Verificare la sintassi Python**
  - Run: `python3 -m py_compile backend/app.py`
  - Expected: Esito pulito (exit code 0).

---

### Task 3: Reverse Proxy - Supporto WebSockets in Nginx

**Files:**
- Modify: `proxy/nginx.conf`

**Interfaces:**
- Consumes: Connessioni HTTP e WebSocket su porta 80.
- Produces: Reverse proxy per API e upgrade a WebSocket verso `backend:8000`.

- [ ] **Step 1: Aggiungere direttive WebSocket e proxy headers in `proxy/nginx.conf`**
  - Nella sezione `location /api`, aggiungere:
    ```nginx
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    ```

---

### Task 4: Frontend Fixes - `Auth.vue`, `UserManagement2.vue`, `HealthCheck.vue`, Routing e Layout

**Files:**
- Modify: `frontend/src/components/Auth.vue`
- Modify: `frontend/src/components/UserManagement2.vue`
- Modify: `frontend/src/components/HealthCheck.vue`
- Modify: `frontend/src/router.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/main.js`

**Interfaces:**
- Consumes: API backend su path `/api/...`.
- Produces: Navigazione coerente senza crash JS, routing protetto, real-time funzionante, rimozione dipendenza da URL hardcoded `http://localhost:5000`.

- [ ] **Step 1: Correggere `frontend/src/components/Auth.vue`**
  - Importare `useRouter` da `vue-router` e inizializzare `const router = useRouter()`.
  - Verificare che il login reindirizzi correttamente senza sollevare `ReferenceError: router is not defined`.

- [ ] **Step 2: Allineare Socket.IO in `frontend/src/components/UserManagement2.vue`**
  - Nel listener WebSocket, ascoltare `'users_update'` (coerente con il backend):
    `socket.on('users_update', (data) => { users.value = data; });`.

- [ ] **Step 3: Rimuovere URL hardcoded in `HealthCheck.vue` e `main.js`**
  - In `frontend/src/components/HealthCheck.vue`: usare `/api/health` anziché `http://localhost:5000/api/health`.
  - In `frontend/src/main.js`: impostare `axios.defaults.baseURL = import.meta.env.VITE_API_URL || ''`.

- [ ] **Step 4: Pulizia del router (`frontend/src/router.js`) e Navbar (`App.vue`)**
  - Indirizzare la rotta `/users` direttamente a `UserManagement2.vue` (o renderlo il componente principale, mantenendo compatibilità).
  - Correggere il refuso nel template di `App.vue`: `"Healthchek"` -> `"Health Check"`.

---

### Task 5: Automated Backend Tests con Pytest

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_api.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: Applicazione Flask configurata con test client in-memory (SQLite per test rapidi).
- Produces: Test automatizzati per healthcheck, signup, signin JWT, login, db-explorer e sicurezza SQLi.

- [ ] **Step 1: Aggiungere `pytest` a `backend/requirements.txt`**
  - Inserire `pytest>=7.0.0`.

- [ ] **Step 2: Creare `backend/tests/conftest.py` con fixture per app e client**
  - Configurare l'app in modalità `TESTING = True` con DB SQLite in memoria (`sqlite:///:memory:`).
  - Inizializzare le tabelle prima di ogni test e ripulire al termine.

- [ ] **Step 3: Creare `backend/tests/test_api.py`**
  - Test `test_health_check`: verifica che `/api/health` risponda con 200.
  - Test `test_signup_and_signin_jwt`: verifica registrazione utente e successivo rilascio del token JWT tramite `/api/signin`.
  - Test `test_signin_invalid_credentials`: verifica che credenziali errate restituiscano 401.
  - Test `test_db_explorer_tables`: verifica che `/api/db-explorer` elenchi le tabelle dello schema.
  - Test `test_db_explorer_sqli_protection`: verifica che un nome tabella inesistente/malevolo restituisca 404 senza eseguire SQL arbitrario.

- [ ] **Step 4: Eseguire la suite di test**
  - Run: `pytest backend/tests -v`
  - Expected: Tutti i test passano con successo (5/5 passed).

---

### Task 6: Verifica Finale e Commit Git Firmato

**Files:**
- Repository Git

**Interfaces:**
- Consumes: File modificati e verificati.
- Produces: Commit firmato GPG con chiave `A62BFD763FD350B1`.

- [ ] **Step 1: Ispezione `git status` e `git diff`**
  - Verificare i file modificati ed escludere file non tracciati indesiderati.

- [ ] **Step 2: Esecuzione del commit GPG firmato**
  ```bash
  git add backend/ frontend/ proxy/ .env.dev .env.prod docs/superpowers/plans/
  git -c user.signingkey=A62BFD763FD350B1 commit -S -m "fix: consolidamento erp9lli, bug bloccanti, sicurezza e suite test"
  ```

- [ ] **Step 3: Verifica esito commit con `git status` e `git log -n 1`**
  - Run: `git status && git log -n 1 --show-signature`
  - Expected: Working tree pulito e firma GPG valida visualizzata.
