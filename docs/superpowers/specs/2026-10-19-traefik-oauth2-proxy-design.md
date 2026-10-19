# Specifica Architetturale: Autenticazione OIDC con Traefik v3 e oauth2-proxy (Full Edge Auth)

## 1. Obiettivo e Panoramica

Integrare l'autenticazione federata **OAuth2 / OpenID Connect (OIDC)** nell'applicazione `erp9lli` adottando l'architettura **Full Edge Auth**:
- **Traefik v3** come Edge Reverse Proxy pubblico con supporto nativo TLS (Let's Encrypt), Security Headers e Rate Limiting.
- **`oauth2-proxy`** come gestore dell'handshake OIDC, dello scambio token, dei cookie cifrati e dell'iniezione degli header di identità tramite il middleware `ForwardAuth` di Traefik.
- **Backend Flask** snello e disaccoppiato dall'Identity Provider: riceve gli header verificati (`X-Forwarded-Email`, `X-Forwarded-User`, `X-Forwarded-Groups`), gestisce l'auto-provisioning nel database locale PostgreSQL e applica il controllo degli accessi basato sui ruoli.
- **Frontend Vue 3**: interroga l'endpoint `/api/me` al boot e reindirizza a `/oauth2/start` per l'accesso e `/oauth2/sign_out` per la disconnessione.
- **Suite di Test**: verifica completa e deterministica sia lato backend (Pytest per auto-provisioning e role mapping) che frontend (Vitest per flussi di interfaccia).

---

## 2. Topologia dei Container e Rete Docker

In produzione, l'infrastruttura è orchestrata tramite `docker-compose.yaml` e `docker-compose.prod.yaml`:

```
                                  CLIENT / BROWSER
                                         │
                                  [Port 80 / 443]
                                         ▼
                     ┌───────────────────────────────────────┐
                     │             TRAEFIK (v3)              │
                     │ - Entrypoints: web (80), websecure(443)│
                     │ - ACME / Let's Encrypt TLS automatico │
                     │ - Middleware: secHeaders, rateLimit   │
                     │ - Middleware: oauth-auth (ForwardAuth)│
                     └───────────────────┬───────────────────┘
                                         │
                  ┌──────────────────────┴──────────────────────┐
                  │ 1. Subrequest interna di verifica           │ 2. Traffico autorizzato
                  ▼                                             ▼
       ┌─────────────────────┐                    ┌───────────────────────────┐
       │    oauth2-proxy     │                    │ Router Traefik:           │
       │ - Porta 4180        │                    │ - Path `/`    -> Frontend │
       │ - Sessione cifrata  │                    │ - Path `/api` -> Backend  │
       │ - Inietta headers   │                    └─────────────┬─────────────┘
       └──────────┬──────────┘                                  │
                  │ (Handshake OIDC)             ┌──────────────┴──────────────┐
                  ▼                              ▼                             ▼
       ┌─────────────────────┐        ┌─────────────────────┐       ┌─────────────────────┐
       │  Identity Provider  │        │   Frontend Static   │       │    Backend Flask    │
       │ (Keycloak, Google,  │        │ (Nginx dist Vue SPA)│       │  (Port 8000 interne)│
       │  Azure, Okta)       │        └─────────────────────┘       └──────────┬──────────┘
       └─────────────────────┘                                                 │
                                                                      ┌────────┴────────┐
                                                                      ▼                 ▼
                                                           ┌────────────────┐  ┌────────────────┐
                                                           │ PostgreSQL 15  │  │  Redis Alpine  │
                                                           └────────────────┘  └────────────────┘
```

### 2.1 Servizi Definiti
1. **`traefik`**:
   - Immagine: `traefik:v3.1`.
   - Porte esposte sull'host: `80:80` (redirect automatico HTTPS) e `443:443` (TLS termination).
   - Socket Docker: `/var/run/docker.sock:ro`.
   - Volume: `traefik_acme:/etc/traefik/acme` per persistenza certificati.
2. **`oauth2-proxy`**:
   - Immagine: `quay.io/oauth2-proxy/oauth2-proxy:v7.6.0`.
   - Porta interna: `4180` (non esposta sull'host).
   - Configurazione OIDC tramite variabili d'ambiente.
3. **`frontend` (Static Web Server)**:
   - Sostituisce il reverse proxy manuale Nginx: container minimale Nginx che serve i file generati da `npm run build` su porta 80 interna.
4. **`backend`**:
   - Gunicorn con gevent worker su porta 8000 interna (non esposta sull'host).

---

## 3. Flusso di Autenticazione ForwardAuth

### 3.1 Middleware Traefik
- **`oauth-auth` (ForwardAuth)**:
  - `address`: `http://oauth2-proxy:4180/oauth2/auth`
  - `trustForwardHeader`: `true`
  - `authResponseHeaders`: `X-Forwarded-User,X-Forwarded-Email,X-Forwarded-Preferred-Username,X-Forwarded-Groups`
- **`oauth-errors` (ErrorPage)**:
  - `status`: `401`
  - `service`: `oauth2-proxy`
  - `query`: `/oauth2/start?rd={url}`

### 3.2 Rotte e Priorità
- **Rotte Protette** (`/` e `/api`):
  - Hanno applicati i middleware `secHeaders`, `rateLimit`, `oauth-errors`, `oauth-auth`.
- **Rotte Escluse (Bypass / Whitelist)**:
  - `/oauth2/*`: instradato direttamente a `oauth2-proxy:4180` con priorità elevata, senza middleware di auth.
  - `/api/health`: opzionalmente senza `oauth-auth` per permettere l'uptime monitoring esterno.

---

## 4. Specifiche Backend Flask

### 4.1 Modello Dati (`models.py`)
Nel modello `User`:
- `password_hash`: resa opzionale (`nullable=True`), poiché gli utenti federati OIDC non possiedono password locale.
- `oauth_provider`: String(50), default `'oidc'` (nullable=True).

### 4.2 Risoluzione Identità ed Endpoint `/api/me`
Nuovo endpoint `GET /api/me`:
1. Legge gli header `X-Forwarded-Email`, `X-Forwarded-Preferred-Username` (o `X-Forwarded-User`), `X-Forwarded-Groups`.
2. Se `X-Forwarded-Email` è assente:
   - In ambiente di sviluppo (`FLASK_ENV=development`): esegue fallback su `DEV_AUTH_USER` (default `dev@example.com`).
   - In produzione: restituisce `401 Unauthorized` (`{"authenticated": false}`).
3. Se l'utente non è presente nel database:
   - Auto-provisioning con inserimento a DB.
   - Ruolo assegnato: `'Admin'` se nei gruppi è presente `"admin"` (case-insensitive), altrimenti `'User'`.
4. Restituisce il payload JSON:
   ```json
   {
     "authenticated": true,
     "id": 1,
     "email": "user@example.com",
     "username": "user",
     "role": "Admin"
   }
   ```

### 4.3 Controllo degli Accessi (`@require_auth`)
Decoratore applicabile alle rotte protette:
- Verifica la presenza dell'identità.
- Se specificato `roles=['Admin']`, verifica che `user.role` sia autorizzato; in caso contrario restituisce `403 Forbidden`.

---

## 5. Specifiche Frontend Vue 3

### 5.1 Riconciliazione Sessione
- All'avvio dell'applicazione (`App.vue` / router guard):
  - Chiamata a `GET /api/me`.
  - Se `authenticated: true`: salva le info utente nello stato reattivo e consente l'accesso alle rotte protette.
  - Se `authenticated: false`: la rotta `/auth` mostra il pulsante *"Accedi con SSO"*, il cui link punta a `/oauth2/start?rd=/dashboard`.

### 5.2 Logout
- Il pulsante "Logout" nella barra di navigazione reindirizza il browser a:
  `/oauth2/sign_out?rd=/`
  Questo invalida il cookie di sessione di `oauth2-proxy` e reindirizza alla home pubblica.

---

## 6. Configurazione e Variabili d'Ambiente

Nel file `.env.prod`:
```ini
# Configurazione Traefik
TRAEFIK_DOMAIN=erp.example.com
ACME_EMAIL=admin@example.com

# Configurazione oauth2-proxy
OAUTH2_PROXY_PROVIDER=oidc
OAUTH2_PROXY_CLIENT_ID=your-client-id
OAUTH2_PROXY_CLIENT_SECRET=your-client-secret
OAUTH2_PROXY_OIDC_ISSUER_URL=https://auth.example.com/realms/erp
OAUTH2_PROXY_COOKIE_SECRET=32-bytes-random-aes-secret-key-1234
OAUTH2_PROXY_COOKIE_SECURE=true
OAUTH2_PROXY_EMAIL_DOMAINS=*
OAUTH2_PROXY_SCOPE=openid profile email groups
```

Nel file `.env.dev`:
```ini
FLASK_ENV=development
DEV_AUTH_USER=dev@example.com
DEV_AUTH_ROLE=Admin
```

---

## 7. Strategia di Test Automatizzati

### 7.1 Backend (`tests/backend/test_forward_auth.py`)
1. `test_anonymous_request_rejected`: richiesta a `/api/me` senza header restituisce 401.
2. `test_auto_provisioning_standard_user`: richiesta con `X-Forwarded-Email: new@example.com` crea l'utente con ruolo `User`.
3. `test_auto_provisioning_admin_role_mapping`: richiesta con `X-Forwarded-Groups: erp-admins` crea l'utente con ruolo `Admin`.
4. `test_protected_route_authorization`:
   - Chiamata a `/api/users` da utente anonimo -> 401.
   - Chiamata da utente con ruolo `User` -> 403 Forbidden.
   - Chiamata da utente con ruolo `Admin` -> 200 OK.
5. `test_dev_mode_fallback`: in modalità development, l'assenza di header fa fallback controllato su `DEV_AUTH_USER`.

### 7.2 Frontend (`tests/frontend/AuthForward.spec.js`)
1. `test_renders_sso_button_when_unauthenticated`: mostra il pulsante SSO con link `/oauth2/start`.
2. `test_populates_user_profile_when_authenticated`: aggiorna l'interfaccia con username e ruolo dopo `/api/me`.
3. `test_logout_redirects_to_oauth2_sign_out`: verifica che l'azione di logout punti a `/oauth2/sign_out`.

### 7.3 Validazione Docker
- Esecuzione di `docker compose -f docker-compose.yaml -f docker-compose.prod.yaml config` per certificare la coerenza delle labels Traefik.
