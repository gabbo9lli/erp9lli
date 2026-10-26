#!/usr/bin/env python3
"""
erp9lli - Deploy Automatico su AWS EC2 (K3s su Ubuntu 24.04 LTS ARM64 Graviton)
Esecuzione: uv run --with boto3 python scripts/deploy_aws.py
"""
import os
import sys
import time
import json
import base64
from pathlib import Path

def load_env_aws():
    env_file = Path(".env.aws")
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().replace('"', '').replace("'", ""))

def main():
    load_env_aws()

    print("=" * 70)
    print("🚀 DEPLOY AUTOMATICO: erp9lli su AWS (K3s / Ubuntu 24.04 Graviton)")
    print("=" * 70)

    # 1. Recupero Credenziali AWS
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_DEFAULT_REGION", "eu-west-1") # Default Irlanda

    if not aws_key:
        aws_key = input("Inserisci AWS_ACCESS_KEY_ID: ").strip()
    if not aws_secret:
        aws_secret = input("Inserisci AWS_SECRET_ACCESS_KEY: ").strip()

    if not aws_key or not aws_secret:
        print("❌ Errore: Credenziali AWS obbligatorie.")
        sys.exit(1)

    print(f"\n📍 Regione AWS selezionata: {aws_region} (Irlanda)")

    import boto3
    from botocore.exceptions import ClientError

    ec2 = boto3.client(
        "ec2",
        region_name=aws_region,
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret
    )

    state_file = Path("aws-state.json")
    if state_file.exists():
        print(f"⚠️ Attenzione: Trovato file {state_file}. Un'installazione potrebbe essere già attiva.")
        resp = input("Vuoi continuare sovrascrivendo le risorse registrate? (s/N): ").strip().lower()
        if resp != "s":
            print("Operazione annullata.")
            sys.exit(0)

    # 2. Ricerca AMI Ubuntu 24.04 LTS ARM64 ufficiale (Canonical)
    print("\n🔍 Ricerca AMI ufficiale Ubuntu 24.04 LTS ARM64...")
    try:
        images_resp = ec2.describe_images(
            Owners=["099720109477"], # Canonical ID
            Filters=[
                {"Name": "name", "Values": ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-arm64-server-*"]},
                {"Name": "state", "Values": ["available"]}
            ]
        )
        images = sorted(images_resp.get("Images", []), key=lambda x: x["CreationDate"], reverse=True)
        if not images:
            raise RuntimeError("Nessuna AMI Ubuntu 24.04 ARM64 trovata.")
        ami_id = images[0]["ImageId"]
        print(f"   AMI individuata: {ami_id} ({images[0]['Name']})")
    except Exception as e:
        print(f"❌ Errore nel recupero dell'AMI: {e}")
        sys.exit(1)

    # 3. Creazione o recupero KeyPair SSH
    key_name = "erp9lli-aws-key"
    key_file = Path(f"{key_name}.pem")
    print(f"\n🔑 Configurazione coppia chiavi SSH ({key_name})...")
    try:
        ec2.delete_key_pair(KeyName=key_name)
    except Exception:
        pass

    try:
        key_resp = ec2.create_key_pair(KeyName=key_name, KeyType="ed25519")
        key_file.write_text(key_resp["KeyMaterial"])
        key_file.chmod(0o400)
        print(f"   Chiave privata salvata in: {key_file.resolve()} (permessi protetti 400)")
    except Exception as e:
        print(f"❌ Errore nella creazione della chiave SSH: {e}")
        sys.exit(1)

    # 4. Creazione Security Group (Porte 80, 443, 22)
    sg_name = "erp9lli-k8s-sg"
    print(f"\n🛡️ Configurazione Security Group ({sg_name})...")
    
    # Recupero VPC predefinita
    vpcs_resp = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
    vpcs = vpcs_resp.get("Vpcs", [])
    if not vpcs:
        vpcs_resp = ec2.describe_vpcs()
        vpcs = vpcs_resp.get("Vpcs", [])
    vpc_id = vpcs[0]["VpcId"]
    print(f"   VPC utilizzata: {vpc_id}")

    try:
        sg_resp = ec2.create_security_group(
            GroupName=f"{sg_name}-{int(time.time())}",
            Description="Security Group per cluster erp9lli K3s",
            VpcId=vpc_id
        )
        sg_id = sg_resp["GroupId"]
        print(f"   Security Group creato: {sg_id}")

        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 80,
                    "ToPort": 80,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTP Web"}]
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 443,
                    "ToPort": 443,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTPS WebSecure"}]
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH Admin"}]
                }
            ]
        )
        print("   Regole in ingresso abilitate: 80 (HTTP), 443 (HTTPS), 22 (SSH)")
    except Exception as e:
        print(f"❌ Errore nella creazione del Security Group: {e}")
        sys.exit(1)

    # 5. Lettura script Cloud-Init per installazione automatica
    cloud_init_file = Path(__file__).parent / "cloud-init.sh"
    user_data_script = cloud_init_file.read_text()

    # 6. Avvio Istanza EC2 (t4g.medium ARM Graviton, 40GB gp3)
    instance_type = "t4g.medium"
    print(f"\n🖥️ Lancio istanza EC2 {instance_type} (40 GB gp3 SSD)...")
    try:
        run_resp = ec2.run_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            KeyName=key_name,
            SecurityGroupIds=[sg_id],
            MinCount=1,
            MaxCount=1,
            UserData=user_data_script,
            BlockDeviceMappings=[
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {
                        "VolumeSize": 40,
                        "VolumeType": "gp3",
                        "DeleteOnTermination": True
                    }
                }
            ],
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Name", "Value": "erp9lli-k8s-server"},
                        {"Key": "Project", "Value": "erp9lli"}
                    ]
                }
            ]
        )
        instance_id = run_resp["Instances"][0]["InstanceId"]
        print(f"   Istanza avviata: {instance_id}. Attesa stato 'Running'...")

        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id])
        print("   Istanza attiva e funzionante.")
    except Exception as e:
        print(f"❌ Errore nel lancio dell'istanza: {e}")
        sys.exit(1)

    # 7. Allocazione e Associazione Elastic IP (IP statico pubblico)
    print("\n🌐 Allocazione Elastic IP pubblico statico...")
    try:
        eip_resp = ec2.allocate_address(Domain="vpc")
        alloc_id = eip_resp["AllocationId"]
        public_ip = eip_resp["PublicIp"]
        print(f"   Elastic IP allocato: {public_ip} ({alloc_id})")

        ec2.associate_address(
            InstanceId=instance_id,
            AllocationId=alloc_id
        )
        print(f"   Elastic IP {public_ip} associato all'istanza {instance_id}")
    except Exception as e:
        print(f"❌ Errore nell'allocazione dell'Elastic IP: {e}")
        sys.exit(1)

    # 8. Salvataggio stato locale per gestione e destroy sicuro
    state_data = {
        "region": aws_region,
        "instance_id": instance_id,
        "allocation_id": alloc_id,
        "elastic_ip": public_ip,
        "security_group_id": sg_id,
        "key_name": key_name,
        "key_file": str(key_file)
    }
    state_file.write_text(json.dumps(state_data, indent=2))

    print("\n" + "=" * 70)
    print("🎉 PROVISIONING AWS COMPLETATO CON SUCCESSO!")
    print("=" * 70)
    print(f"• Indirizzo IP Pubblico dell'applicazione: http://{public_ip}")
    print(f"• Connessione SSH: ssh -i {key_file} ubuntu@{public_ip}")
    print(f"• File di stato salvato in: {state_file}")
    print("\n⏳ NOTA:")
    print("La macchina sta completando in background l'installazione di K3s e il deploy dei container.")
    print("L'applicazione sarà completamente attiva tra circa 3-4 minuti all'indirizzo:")
    print(f"👉 http://{public_ip}")
    print("\nPer monitorare il completamento dell'installazione in tempo reale puoi eseguire:")
    print(f"ssh -i {key_file} ubuntu@{public_ip} 'sudo tail -f /var/log/cloud-init-output.log'")
    print("=" * 70)

if __name__ == "__main__":
    main()
