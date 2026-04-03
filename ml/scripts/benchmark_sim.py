"""
Benchmark Simulator 
===================
Runs 100 simulated transaction requests through the ML pipeline to measure
latency and security overhead, generating a graph of "Accuracy vs Latency".
"""

import os
import time
import random
import requests
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm

API_URL = "http://127.0.0.1:8000/api/v1/voice/process-text"
USER_ID = "demo_user"
NUM_SIMULATIONS = 100

INTENTS = ["send_money", "check_balance", "transaction_history", "pay_bill"]
TEXT_TEMPLATES = [
    "send {amount} to rahul",
    "what is my balance",
    "show last 5 transactions",
    "pay electricity bill of {amount}"
]

def simulate():
    print(f"========================================")
    print(f"🚀 Risk-Adaptive Pipeline Simulator")
    print(f"========================================")
    print(f"Sending {NUM_SIMULATIONS} requests to backend...")
    
    results = []
    
    # Needs a slight delay if server just started
    time.sleep(2)

    for i in tqdm(range(NUM_SIMULATIONS)):
        intent_idx = random.randint(0, 3)
        amount = random.choice([50, 100, 500, 5000, 10000])
        
        text = TEXT_TEMPLATES[intent_idx].format(amount=amount)
        
        # Randomly toggle sv_override to simulate enrolled vs non-enrolled paths
        sv_override = random.choice([True, False])
        
        start_time = time.time()
        try:
            resp = requests.post(API_URL, data={
                "text": text,
                "user_id": USER_ID,
                "sv_override": str(sv_override).lower()
            }, timeout=10)
            
            end_time = time.time()
            latency = (end_time - start_time) * 1000  # ms
            
            if resp.status_code == 200:
                data = resp.json()
                auth_req = data.get("auth_decision", {}).get("auth_required", "unknown")
                risk = data.get("auth_decision", {}).get("risk_tier", "unknown")
                results.append({
                    "run": i,
                    "text": text,
                    "intent": INTENTS[intent_idx],
                    "sv_override": sv_override,
                    "latency_ms": latency,
                    "risk_tier": risk,
                    "auth_required": auth_req,
                    "status": "success"
                })
            else:
                results.append({
                    "run": i,
                    "text": text,
                    "intent": INTENTS[intent_idx],
                    "sv_override": sv_override,
                    "latency_ms": latency,
                    "status": f"failed_{resp.status_code}"
                })
        except Exception as e:
            results.append({
                "run": i,
                "text": text,
                "intent": INTENTS[intent_idx],
                "sv_override": sv_override,
                "latency_ms": 0,
                "status": "error"
            })
            
    # Compile results
    df = pd.DataFrame(results)
    
    # Filter successes
    df_success = df[df["status"] == "success"]
    
    print("\n========================================")
    print("📊 Simulation Results")
    print("========================================")
    print(f"Total Requests: {len(df)}")
    print(f"Successful:   {len(df_success)}")
    print(f"Failed/Error: {len(df) - len(df_success)}")
    
    if not df_success.empty:
        print(f"\nAverage Latency: {df_success['latency_ms'].mean():.2f} ms")
        print(f"Min Latency:     {df_success['latency_ms'].min():.2f} ms")
        print(f"Max Latency:     {df_success['latency_ms'].max():.2f} ms")
        
        print("\nLatency by Intent:")
        print(df_success.groupby('intent')['latency_ms'].mean().to_string())
        
        print("\nRisk Tier Distribution:")
        print(df_success['risk_tier'].value_counts().to_string())

        # Generate Plot
        os.makedirs("ml/data", exist_ok=True)
        csv_path = "ml/data/benchmark_results.csv"
        df.to_csv(csv_path, index=False)
        
        plt.figure(figsize=(10, 6))
        
        # Plot latency distribution by Intent
        intents_found = df_success['intent'].unique()
        data_to_plot = [df_success[df_success['intent'] == i]['latency_ms'] for i in intents_found]
        
        plt.boxplot(data_to_plot, labels=intents_found, patch_artist=True)
        plt.title('Pipeline Latency by Intent Complexity')
        plt.ylabel('Latency (ms)')
        plt.xlabel('Intent Type')
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        
        plot_path = "ml/data/benchmark_latency_plot.png"
        plt.savefig(plot_path)
        print(f"\n✅ Results saved to {csv_path}")
        print(f"✅ Plot saved to {plot_path}")
    
if __name__ == "__main__":
    simulate()
