"""
Database Initialization Script
================================
Creates all tables and seeds a demo user.

Usage: python scripts/init_db.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.config import get_config
from backend.app.db.database import init_db, Base
from backend.app.db.models import User, SpeakerProfile, Transaction, AuditLog


def init():
    """Initialize database and seed demo data."""
    print("=" * 60)
    print("Database Initialization")
    print("=" * 60)

    config = get_config()

    # Ensure storage directory exists
    os.makedirs("storage", exist_ok=True)

    # Initialize engine
    engine, SessionLocal = init_db(config.database_url)

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print(f"[DB] Tables created: {', '.join(Base.metadata.tables.keys())}")

    # Seed demo user
    session = SessionLocal()
    try:
        # Check if demo user exists
        existing = session.query(User).filter_by(username="demo_user").first()
        if existing:
            print(f"[DB] Demo user already exists (id={existing.id})")
        else:
            # Create demo user with PIN "1234"
            import bcrypt
            pin_hash = bcrypt.hashpw("1234".encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

            demo_user = User(
                username="demo_user",
                display_name="Demo User",
                pin_hash=pin_hash,
                balance=10000.0,
                is_active=True,
            )
            session.add(demo_user)
            session.commit()
            session.refresh(demo_user)

            print(f"[DB] Demo user created:")
            print(f"  Username: demo_user")
            print(f"  Display Name: Demo User")
            print(f"  PIN: 1234 (hashed)")
            print(f"  Balance: ₹10,000")
            print(f"  ID: {demo_user.id}")

            # Create empty speaker profile
            profile = SpeakerProfile(
                user_id=demo_user.id,
                embedding_path=f"storage/speaker_profiles/demo_user.npy",
                num_enrollment_samples=0,
                is_enrolled=False,
            )
            session.add(profile)
            session.commit()
            print(f"[DB] Speaker profile placeholder created (not enrolled yet)")

        # Print table counts
        print(f"\n[DB] Table summary:")
        print(f"  Users:            {session.query(User).count()}")
        print(f"  Speaker Profiles: {session.query(SpeakerProfile).count()}")
        print(f"  Transactions:     {session.query(Transaction).count()}")
        print(f"  Audit Logs:       {session.query(AuditLog).count()}")

    except Exception as e:
        session.rollback()
        print(f"[DB] Error: {e}")
        raise
    finally:
        session.close()

    print(f"\n✅ Database initialized at: {config.database_url}")


if __name__ == "__main__":
    init()
