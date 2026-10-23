from database import SessionLocal
from models import User

def seed_data():
    with SessionLocal() as db:
        # Check if we already have users
        if not db.query(User).first():
            print("Seeding database...")
            test_user = User(username='dev@example.com', email='dev@example.com', role='Admin')
            test_user.set_password('DevPassword123!')
            db.add(test_user)
            db.commit()
            print("Seed complete.")
        else:
            print("Database already has data, skipping seed.")

if __name__ == "__main__":
    seed_data()
