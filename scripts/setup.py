"""
Full Project Setup Script
===========================
One-command setup for the Risk-Adaptive Voice Finance Assistant.
Handles: dependency installation, dataset generation, model training, and DB initialization.

Usage: python scripts/setup.py
"""

import os
import sys
import subprocess
import time

# Fix Windows terminal encoding — prevent cp1252 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure we run from project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

DIVIDER = "=" * 60


def run_cmd(cmd, desc, cwd=None):
    """Run a shell command with status output."""
    print(f"\n{'─' * 40}")
    print(f"  {desc}...")
    print(f"   $ {cmd}")
    # Force UTF-8 for child processes on Windows
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(cmd, shell=True, cwd=cwd or PROJECT_ROOT,
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            env=env)
    if result.returncode != 0:
        print(f"   ❌ FAILED")
        print(f"   STDOUT: {result.stdout[-300:]}" if result.stdout else "")
        print(f"   STDERR: {result.stderr[-300:]}" if result.stderr else "")
        return False
    print(f"   ✅ Done")
    return True


def run_python(script, desc):
    """Run a Python script."""
    return run_cmd(f'python "{script}"', desc)


def main():
    start = time.time()

    print(DIVIDER)
    print("🚀 Risk-Adaptive Voice Finance Assistant — Full Setup")
    print(DIVIDER)
    print(f"Project root: {PROJECT_ROOT}")

    # ─── Step 1: Python Dependencies ───
    print(f"\n\n{'█' * 60}")
    print("█  STEP 1/6: Python Dependencies")
    print(f"{'█' * 60}")

    ok = run_cmd("pip install -r requirements.txt",
                 "Installing Python dependencies")
    if not ok:
        print("⚠️  Some packages may not have installed. Continuing...")

    # ─── Step 2: Frontend Dependencies ───
    print(f"\n\n{'█' * 60}")
    print("█  STEP 2/6: Frontend Dependencies")
    print(f"{'█' * 60}")

    frontend_dir = os.path.join(PROJECT_ROOT, "frontend")
    if os.path.exists(os.path.join(frontend_dir, "package.json")):
        if not os.path.exists(os.path.join(frontend_dir, "node_modules")):
            run_cmd("npm install", "Installing frontend npm packages", cwd=frontend_dir)
        else:
            print("\n   ✅ Frontend dependencies already installed")
    else:
        print("\n   ⚠️  No frontend/package.json found. Skipping npm install.")

    # ─── Step 3: Create Directories ───
    print(f"\n\n{'█' * 60}")
    print("█  STEP 3/6: Directory Structure")
    print(f"{'█' * 60}")

    dirs = [
        "storage/audio", "storage/speaker_profiles", "storage/logs",
        "ml/data", "ml/models",
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    print(f"\n   ✅ Created {len(dirs)} directories")

    # ─── Step 4: Generate Datasets ───
    print(f"\n\n{'█' * 60}")
    print("█  STEP 4/6: Generate Training Datasets")
    print(f"{'█' * 60}")

    run_python("ml/scripts/generate_intent_dataset.py", "Generating intent classification dataset (500 samples)")
    run_python("ml/scripts/generate_fraud_dataset.py", "Generating fraud detection dataset (10,000 samples)")

    # Verify datasets
    intent_path = "ml/data/intent_dataset.csv"
    fraud_path = "ml/data/fraud_dataset.csv"
    if os.path.exists(intent_path):
        lines = sum(1 for _ in open(intent_path)) - 1
        print(f"   📊 Intent dataset: {lines} samples")
    if os.path.exists(fraud_path):
        lines = sum(1 for _ in open(fraud_path)) - 1
        print(f"   📊 Fraud dataset: {lines} samples")

    # ─── Step 5: Train Models ───
    print(f"\n\n{'█' * 60}")
    print("█  STEP 5/6: Train ML Models")
    print(f"{'█' * 60}")

    run_python("ml/scripts/train_intent_model.py", "Training intent classification model (LSTM)")
    run_python("ml/scripts/train_fraud_model.py", "Training fraud detection model (IsolationForest + RandomForest)")

    # Verify models
    models = [
        ("ml/models/intent_model.pth", "Intent model"),
        ("ml/models/vocab.json", "Vocabulary"),
        ("ml/models/fraud_model.joblib", "Fraud model"),
        ("ml/models/fraud_scaler.joblib", "Fraud scaler"),
    ]
    for path, name in models:
        if os.path.exists(path):
            size_kb = os.path.getsize(path) / 1024
            print(f"   📦 {name}: {size_kb:.1f} KB")
        else:
            print(f"   ❌ {name}: NOT FOUND")

    # ─── Step 6: Initialize Database ───
    print(f"\n\n{'█' * 60}")
    print("█  STEP 6/6: Initialize Database")
    print(f"{'█' * 60}")

    run_python("scripts/init_db.py", "Creating tables and seeding demo user")

    # ─── Summary ───
    elapsed = time.time() - start
    print(f"\n\n{DIVIDER}")
    print(f"✅ Setup Complete! ({elapsed:.1f}s)")
    print(DIVIDER)

    # Check .env
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            content = f.read()
        if "XXXXXXX" in content or "rzp_test_XXXXXXX" in content:
            print("\n⚠️  Razorpay keys not configured yet!")
            print("   Edit .env and add your Razorpay test/live keys:")
            print("   RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx")
            print("   RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx")

    print(f"\n🎯 To run the app:")
    print(f"   python scripts/run.py")
    print(f"\n   Or manually:")
    print(f"   Terminal 1: python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000")
    print(f"   Terminal 2: cd frontend && npm run dev")
    print(f"\n   Then open: http://localhost:5173")


if __name__ == "__main__":
    main()
