#!/usr/bin/env python3
"""
erp9lli - Pulizia e Distruzione Totale Risorse AWS (Zero Costi Residui)
Esecuzione: uv run --with boto3 python scripts/destroy_aws.py
"""
import os
import sys
import json
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

    state_file = Path("aws-state.json")
    if not state_file.exists():
        print("❌ File aws-state.json non trovato. Nessuna risorsa AWS registrata da eliminare.")
        sys.exit(0)

    state = json.loads(state_file.read_text())
    region = state.get("region", "eu-west-1")
    instance_id = state.get("instance_id")
    allocation_id = state.get("allocation_id")
    sg_id = state.get("security_group_id")
    key_name = state.get("key_name")
    key_file = Path(state.get("key_file", "erp9lli-aws-key.pem"))

    print("=" * 70)
    print("🧹 DISTRUZIONE TOTALE RISORSE AWS erp9lli (Azzeramento Costi)")
    print("=" * 70)
    print(f"• Regione: {region}")
    print(f"• Istanza EC2: {instance_id}")
    print(f"• Elastic IP Allocation: {allocation_id}")
    print(f"• Security Group: {sg_id}")
    print(f"• Chiave SSH: {key_name}")

    confirm = input("\nSei SICURO di voler distruggere l'istanza e rilasciare l'IP? (digita 'destroy'): ").strip()
    if confirm != "destroy":
        print("Operazione annullata.")
        sys.exit(0)

    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    if not aws_key:
        aws_key = input("Inserisci AWS_ACCESS_KEY_ID: ").strip()
    if not aws_secret:
        aws_secret = input("Inserisci AWS_SECRET_ACCESS_KEY: ").strip()

    import boto3
    ec2 = boto3.client(
        "ec2",
        region_name=region,
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret
    )

    # 1. Disassociazione e Rilascio Elastic IP (evita addebito fantasma di $3.60/mese)
    if allocation_id:
        print("\n🌐 Rilascio Elastic IP da AWS...")
        try:
            # Disassocia se associato
            eips = ec2.describe_addresses(AllocationIds=[allocation_id]).get("Addresses", [])
            for e in eips:
                assoc_id = e.get("AssociationId")
                if assoc_id:
                    ec2.disassociate_address(AssociationId=assoc_id)
            # Rilascia
            ec2.release_address(AllocationId=allocation_id)
            print("   Elastic IP rilasciato con successo (nessun costo residuo).")
        except Exception as e:
            print(f"   ⚠️ Avviso rilascio IP: {e}")

    # 2. Terminazione Istanza EC2 (e disco EBS collegato)
    if instance_id:
        print(f"\n🖥️ Terminazione istanza EC2 {instance_id}...")
        try:
            ec2.terminate_instances(InstanceIds=[instance_id])
            print("   Richiesta di terminazione inviata. Attesa eliminazione...")
            waiter = ec2.get_waiter("instance_terminated")
            waiter.wait(InstanceIds=[instance_id])
            print("   Istanza terminata e volume EBS eliminato.")
        except Exception as e:
            print(f"   ⚠️ Avviso terminazione istanza: {e}")

    # 3. Eliminazione Security Group
    if sg_id:
        print(f"\n🛡️ Eliminazione Security Group {sg_id}...")
        import time
        for _ in range(5):
            try:
                ec2.delete_security_group(GroupId=sg_id)
                print("   Security Group eliminato.")
                break
            except Exception:
                time.sleep(3)

    # 4. Eliminazione KeyPair
    if key_name:
        print(f"\n🔑 Eliminazione chiave SSH {key_name} da AWS...")
        try:
            ec2.delete_key_pair(KeyName=key_name)
            print("   Coppia di chiavi eliminata da AWS.")
        except Exception as e:
            print(f"   ⚠️ Avviso chiave SSH: {e}")

    # 5. Pulizia file locali
    if key_file.exists():
        key_file.unlink()
        print(f"   File locale {key_file} rimosso.")

    if state_file.exists():
        state_file.unlink()
        print(f"   File di stato {state_file} rimosso.")

    print("\n" + "=" * 70)
    print("✅ PULIZIA COMPLETATA: Tutte le risorse AWS sono state distrutte.")
    print("I costi orari e fissi per questa installazione sono ora 0,00 €.")
    print("=" * 70)

if __name__ == "__main__":
    main()
