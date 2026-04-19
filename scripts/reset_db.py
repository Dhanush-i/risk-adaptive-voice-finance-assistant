"""
Reset Database — Fresh start for demos
=======================================
Deletes the SQLite database and speaker profiles so you get a clean slate.

Usage:
    python scripts/reset_db.py
"""

import os
import shutil
import glob

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files and folders to clean
TARGETS = [
    os.path.join(PROJECT_ROOT, "storage", "voice_finance.db"),
    os.path.join(PROJECT_ROOT, "storage", "speaker_profiles"),
    os.path.join(PROJECT_ROOT, "storage", "audio"),
    os.path.join(PROJECT_ROOT, "storage", "user_profiles"),
]

def reset():
    print("=" * 50)
    print("🗑️  VoicePay — Database Reset")
    print("=" * 50)

    for target in TARGETS:
        if os.path.isfile(target):
            os.remove(target)
            print(f"  ✓ Deleted file: {os.path.basename(target)}")
        elif os.path.isdir(target):
            shutil.rmtree(target)
            os.makedirs(target, exist_ok=True)
            print(f"  ✓ Cleared folder: {os.path.basename(target)}/")
        else:
            print(f"  - Not found (already clean): {os.path.basename(target)}")

    # Recreate storage directories
    for d in ["storage/audio", "storage/speaker_profiles", "storage/user_profiles", "storage/logs"]:
        os.makedirs(os.path.join(PROJECT_ROOT, d), exist_ok=True)

    print()
    print("✅ Database reset complete!")
    print("   Next time you start the app, it will create a fresh database.")
    print("   Re-register your demo_user with: demo_user / 1234")
    print()

if __name__ == "__main__":
    reset()
