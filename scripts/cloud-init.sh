#!/bin/bash
set -ex

echo "=== [1/6] Inizializzazione Sistema Ubuntu 24.04 LTS ARM64 ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y curl git docker.io ufw fail2ban

echo "=== [2/6] Installazione K3s (Lightweight Kubernetes) ==="
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644

# Configura kubectl per root e utente ubuntu
mkdir -p /home/ubuntu/.kube
cp /etc/rancher/k3s/k3s.yaml /home/ubuntu/.kube/config
chown -R ubuntu:ubuntu /home/ubuntu/.kube

echo "Attesa disponibilità nodo K3s..."
until k3s kubectl get nodes | grep -q "Ready"; do
  sleep 3
done

echo "=== [3/6] Download Repository erp9lli ==="
rm -rf /opt/erp9lli
git clone https://github.com/gabbo9lli/erp9lli.git /opt/erp9lli
cd /opt/erp9lli

echo "=== [4/6] Build Immagini di Produzione in Locale ==="
# Costruisce backend di produzione
docker build --target production -t ghcr.io/gabbo9lli/erp9lli-backend:latest ./backend
# Costruisce frontend di produzione (SPA precompilata con Nginx)
docker build --target production -t ghcr.io/gabbo9lli/erp9lli-frontend:latest ./frontend

echo "Importazione immagini nel container runtime di K3s..."
docker save ghcr.io/gabbo9lli/erp9lli-backend:latest | k3s ctr images import -
docker save ghcr.io/gabbo9lli/erp9lli-frontend:latest | k3s ctr images import -

echo "=== [5/6] Deploy dei Manifesti Kubernetes erp9lli ==="
k3s kubectl apply -f k8s/00-namespace.yaml
k3s kubectl apply -f k8s/01-configmap.yaml
k3s kubectl apply -f k8s/02-secrets.yaml
k3s kubectl apply -f k8s/03-postgres.yaml
k3s kubectl apply -f k8s/04-redis.yaml

echo "Attesa avvio database PostgreSQL..."
k3s kubectl wait --namespace erp9lli --for=condition=ready pod -l app=erp9lli-postgres --timeout=180s || true

echo "Esecuzione Job Migrazioni e Seed Iniziale..."
k3s kubectl apply -f k8s/05-migration-job.yaml
k3s kubectl wait --namespace erp9lli --for=condition=complete job/erp9lli-db-migration --timeout=180s || true

echo "Avvio Backend, Worker, Frontend e Ingress..."
k3s kubectl apply -f k8s/06-backend.yaml
k3s kubectl apply -f k8s/07-worker.yaml
k3s kubectl apply -f k8s/08-frontend.yaml
k3s kubectl apply -f k8s/09-ingress.yaml

echo "=== [6/6] Verifica Stato Rollout Pods ==="
k3s kubectl wait --namespace erp9lli --for=condition=ready pod -l app=erp9lli-backend --timeout=180s || true
k3s kubectl wait --namespace erp9lli --for=condition=ready pod -l app=erp9lli-frontend --timeout=180s || true

touch /opt/erp9lli/ready.flag
echo "=== DEPLOY COMPLETATO CON SUCCESSO! ==="
