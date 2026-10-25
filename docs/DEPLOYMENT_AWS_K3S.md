# Guida Operativa al Deploy: erp9lli su AWS con K3s (Ubuntu 24.04 LTS)

Questa guida documenta la procedura per pubblicare **erp9lli** su AWS ottenendo il **massimo controllo possibile** sull'infrastruttura e mantenendo il **costo minimo** (~25 - 30 € al mese).

---

## 1. Architettura & Stima dei Costi

| Componente | Tipo Risorsa AWS | Specifiche | Costo Mensile Stimato |
|---|---|---|---|
| **Calcolo & K8s** | EC2 `t4g.medium` (ARM Graviton) | 2 vCPU, 4 GB RAM | **~$24.00** (On-Demand) / ~$15.00 (Savings Plan 1y) |
| **Storage Dati** | EBS `gp3` | 40 GB SSD (3000 IOPS) | **~$3.20** |
| **IP Pubblico** | AWS Elastic IP | 1 IPv4 statico assegnato | **Incluso / Gratuito** |
| **DNS Pubblico** | Route 53 (o DNS esterno) | 1 Hosted Zone + Record A | **~$0.50** (o 0€ su DNS esterno come Cloudflare) |
| **Certificato SSL**| Let's Encrypt (Cert-Manager) | TLS automatico con rinnovo | **Gratuito** |
| **TOTALE** | | | **~25 - 28 € / mese** |

---

## 2. Configurazione AWS (Console o AWS CLI)

### 2.1 Security Group (`erp9lli-k8s-sg`)
Configura le seguenti regole di traffico in ingresso (Inbound Rules):

* **Porta 80 (HTTP):** Sorgente `0.0.0.0/0` (necessaria per il traffico web e per la challenge ACME Let's Encrypt).
* **Porta 443 (HTTPS):** Sorgente `0.0.0.0/0` (traffico cifrato sicuro verso il Traefik Ingress).
* **Porta 22 (SSH):** Solo dal tuo IP pubblico `X.X.X.X/32` (oppure disabilitata se accedi via AWS Systems Manager Session Manager).
* **Porta 6443 (K8s API):** Solo dal tuo IP `X.X.X.X/32` se intendi usare `kubectl` direttamente dal tuo computer.

### 2.2 Avvio Istanza EC2
* **AMI:** Ubuntu Server 24.04 LTS (HVM) — Seleziona Architettura **64-bit (ARM)** per usare le istanze Graviton `t4g`.
* **Instance Type:** `t4g.medium` (2 vCPU, 4 GiB).
* **Volume EBS:** 40 GB `gp3`.
* **Elastic IP:** Alloca un Elastic IP e associalo alla nuova istanza EC2.

### 2.3 Configurazione DNS
Nel pannello del tuo registrar DNS (es. Cloudflare, Route53, Namecheap), crea un record:
* **Tipo:** `A`
* **Nome:** `gestionale.tuodominio.it` (o `@`)
* **Valore:** L'Elastic IP pubblico associato all'EC2.

---

## 3. Installazione K3s su Ubuntu 24.04 (in 2 minuti)

Connettiti all'istanza via SSH:
```bash
ssh -i tua-chiave.pem ubuntu@tuo-elastic-ip
```

Esegui i seguenti comandi per aggiornare il sistema e installare K3s:
```bash
# 1. Aggiornamento sistema
sudo apt update && sudo apt upgrade -y

# 2. Installazione K3s con permessi di lettura per l'utente ubuntu
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644

# 3. Verifica stato nodo
kubectl get nodes
```

Configura `kubectl` per l'utente corrente:
```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
export KUBECONFIG=~/.kube/config
echo "export KUBECONFIG=~/.kube/config" >> ~/.bashrc
```

---

## 4. Build e Pubblicazione Immagini Docker (GHCR)

Dal tuo computer di sviluppo, compila le immagini di produzione (multi-arch o ARM64) e pubblicale su **GitHub Container Registry**:

```bash
# Effettua il login a ghcr.io con un GitHub Personal Access Token (PAT con permessi read/write packages)
echo $GITHUB_TOKEN | docker login ghcr.io -u gabbo9lli --password-stdin

# Build e push Backend (Target production: Uvicorn con 4 workers)
docker build --target production -t ghcr.io/gabbo9lli/erp9lli-backend:latest ./backend
docker push ghcr.io/gabbo9lli/erp9lli-backend:latest

# Build e push Frontend (Target production: Nginx Alpine compresso)
docker build --target production -t ghcr.io/gabbo9lli/erp9lli-frontend:latest ./frontend
docker push ghcr.io/gabbo9lli/erp9lli-frontend:latest
```

---

## 5. Deploy dell'Applicazione nel Cluster K3s

### 5.1 Crea il segreto per il Pull delle Immagini Private
Sull'istanza EC2, crea l'accesso al registro GitHub Packages:

```bash
kubectl create namespace erp9lli

kubectl create secret docker-registry ghcr-secret \
  --namespace=erp9lli \
  --docker-server=ghcr.io \
  --docker-username=gabbo9lli \
  --docker-password=TUO_GITHUB_PAT_TOKEN \
  --docker-email=gabbo9lli@gmail.com
```

### 5.2 Personalizza Segreti e Dominio
Prima del deploy, modifica:
1. `k8s/02-secrets.yaml`: inserisci una password PostgreSQL sicura e una `SECRET_KEY` casuale di almeno 32 caratteri;
2. `k8s/09-ingress.yaml`: sostituisci `gestionale.retebio.it` con il tuo dominio effettivo.

### 5.3 Applica l'intera suite con Kustomize
```bash
# Clona il repo sul server o copia la cartella k8s/
kubectl apply -k k8s/
```

### 5.4 Verifica lo Stato del Rollout
```bash
kubectl get pods -n erp9lli
# Dovresti vedere:
# - erp9lli-postgres-0 (1/1 Running)
# - erp9lli-redis-... (1/1 Running)
# - erp9lli-db-migration-... (0/1 Completed)
# - erp9lli-backend-... (2/2 Running)
# - erp9lli-worker-... (1/1 Running)
# - erp9lli-frontend-... (2/2 Running)
```

---

## 6. Certificato SSL Gratuito Automatico (Let's Encrypt)

K3s include già Traefik. Per ottenere certificati SSL automatici validi:

```bash
# 1. Installa cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.2/cert-manager.yaml

# 2. Crea il ClusterIssuer per Let's Encrypt
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: gabbo9lli@gmail.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            class: traefik
EOF
```

Cert-manager emetterà e rinnoverà automaticamente il certificato HTTPS per il dominio specificato in `k8s/09-ingress.yaml`.

---

## 7. Backup Programmato su AWS S3 (Disaster Recovery)

Per garantire la sicurezza dei dati senza costi aggiuntivi, puoi creare un Kubernetes `CronJob` giornaliero che esegue un dump compresso di PostgreSQL e lo carica su un bucket S3 privato a basso costo (S3 Standard o Glacier Flexible Archive):

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: erp9lli-postgres-backup
  namespace: erp9lli
spec:
  schedule: "0 2 * * *" # Ogni notte alle 02:00 UTC
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: pg-dump
              image: amazon/aws-cli:latest
              command:
                - /bin/sh
                - -c
                - |
                  set -e
                  yum install -y postgresql
                  BACKUP_FILE="erp9lli_backup_$(date +%Y%m%d_%H%M%S).sql.gz"
                  PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h erp9lli-postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > "/tmp/$BACKUP_FILE"
                  aws s3 cp "/tmp/$BACKUP_FILE" "s3://tuo-bucket-backups/database/$BACKUP_FILE"
                  echo "Backup $BACKUP_FILE completato su S3."
              envFrom:
                - secretRef:
                    name: erp9lli-secrets
```
