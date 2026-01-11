from app import app
from models import db, User

def seed_data():
    with app.app_context():
        # Check if we already have users
        if not User.query.first():
            print("Seeding database...")
            test_user = User(email='dev@example.com')
            db.session.add(test_user)
            db.session.commit()
            print("Seed complete.")
        else:
            print("Database already has data, skipping seed.")

if __name__ == "__main__":
    seed_data()