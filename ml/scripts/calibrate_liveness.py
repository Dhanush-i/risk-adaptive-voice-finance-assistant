"""
Liveness Detection Calibration Script
========================================
Generates synthetic live vs. replay audio samples and sweeps the
High-Frequency Energy (HFE) threshold to find the optimal value
using ROC analysis.

Synthetic approach:
  - Live samples: white noise + sine waves at various frequencies including high (6-8kHz)
  - Replay samples: same signals low-pass filtered at 4kHz to simulate speaker frequency roll-off

Output: Optimal threshold, AUC score, and optional ROC plot.

Usage:
    python ml/scripts/calibrate_liveness.py
"""

import os
import sys
import numpy as np
import torch
from typing import Tuple, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def generate_live_audio(duration: float = 3.0, sr: int = 16000) -> np.ndarray:
    """Generate synthetic 'live' audio with full frequency content."""
    t = np.linspace(0, duration, int(sr * duration), dtype=np.float32)

    # Mix of frequencies including high (6-8kHz) — present in live speech
    signal = np.zeros_like(t)

    # Fundamental + harmonics (speech-like)
    for freq in [200, 400, 800, 1200, 2000, 3500, 5000, 6500, 7500]:
        amplitude = max(0.05, 0.3 * np.exp(-freq / 3000))
        signal += amplitude * np.sin(2 * np.pi * freq * t + np.random.uniform(0, 2 * np.pi))

    # Add noise (natural ambient + breath noise)
    signal += 0.02 * np.random.randn(len(t)).astype(np.float32)

    # Normalize
    signal = signal / (np.max(np.abs(signal)) + 1e-9)
    return signal * 0.8


def generate_replay_audio(duration: float = 3.0, sr: int = 16000) -> np.ndarray:
    """Generate synthetic 'replay' audio — low-pass filtered to simulate speaker roll-off."""
    live = generate_live_audio(duration, sr)

    # Apply low-pass filter at 4kHz (speaker roll-off)
    # Using FFT-based filtering
    fft = np.fft.rfft(live)
    freqs = np.fft.rfftfreq(len(live), 1.0 / sr)

    # Aggressive roll-off above 4kHz
    cutoff = 4000
    for i, f in enumerate(freqs):
        if f > cutoff:
            # Sharp roll-off
            attenuation = np.exp(-((f - cutoff) / 500) ** 2)
            fft[i] *= attenuation

    filtered = np.fft.irfft(fft, n=len(live)).astype(np.float32)

    # Also add slight distortion (speaker nonlinearity)
    filtered += 0.01 * np.random.randn(len(filtered)).astype(np.float32)

    return filtered


def compute_hfe_ratio(audio: np.ndarray, sr: int = 16000) -> float:
    """Compute High-Frequency Energy ratio (same algorithm as speaker_verification.py)."""
    tensor_audio = torch.from_numpy(audio.astype(np.float32))

    spectrogram = torch.stft(
        tensor_audio,
        n_fft=1024,
        hop_length=256,
        win_length=1024,
        return_complex=True,
    )
    magnitude = torch.abs(spectrogram)

    bin_6k = int(6000 * 1024 / sr)
    bin_8k = magnitude.shape[0]

    total_energy = torch.sum(magnitude).item()
    high_freq_energy = torch.sum(magnitude[bin_6k:bin_8k, :]).item()

    return high_freq_energy / total_energy if total_energy > 0 else 0.0


def calibrate(
    num_samples: int = 200,
    duration: float = 3.0,
    sr: int = 16000,
    save_plot: bool = True,
) -> Tuple[float, float]:
    """
    Generate live/replay samples, compute HFE ratios, find optimal threshold.

    Returns:
        (optimal_threshold, auc_score)
    """
    print("=" * 60)
    print("Liveness Detection Calibration")
    print("=" * 60)

    # Generate samples
    live_ratios = []
    replay_ratios = []

    print(f"\n[Calibrate] Generating {num_samples} live samples...")
    for i in range(num_samples):
        audio = generate_live_audio(duration, sr)
        ratio = compute_hfe_ratio(audio, sr)
        live_ratios.append(ratio)

    print(f"[Calibrate] Generating {num_samples} replay samples...")
    for i in range(num_samples):
        audio = generate_replay_audio(duration, sr)
        ratio = compute_hfe_ratio(audio, sr)
        replay_ratios.append(ratio)

    live_ratios = np.array(live_ratios)
    replay_ratios = np.array(replay_ratios)

    print(f"\n[Calibrate] Live HFE ratios:   mean={live_ratios.mean():.4f}, "
          f"std={live_ratios.std():.4f}, range=[{live_ratios.min():.4f}, {live_ratios.max():.4f}]")
    print(f"[Calibrate] Replay HFE ratios: mean={replay_ratios.mean():.4f}, "
          f"std={replay_ratios.std():.4f}, range=[{replay_ratios.min():.4f}, {replay_ratios.max():.4f}]")

    # Combine for ROC analysis
    all_ratios = np.concatenate([live_ratios, replay_ratios])
    all_labels = np.concatenate([np.ones(num_samples), np.zeros(num_samples)])

    # Sweep thresholds
    thresholds = np.linspace(
        min(all_ratios.min(), 0.001),
        max(all_ratios.max(), 0.1),
        1000,
    )

    best_threshold = 0.015
    best_accuracy = 0.0
    tpr_list = []
    fpr_list = []

    for t in thresholds:
        predictions = (all_ratios > t).astype(int)
        tp = np.sum((predictions == 1) & (all_labels == 1))
        tn = np.sum((predictions == 0) & (all_labels == 0))
        fp = np.sum((predictions == 1) & (all_labels == 0))
        fn = np.sum((predictions == 0) & (all_labels == 1))

        tpr = tp / (tp + fn + 1e-9)
        fpr = fp / (fp + tn + 1e-9)
        accuracy = (tp + tn) / len(all_labels)

        tpr_list.append(tpr)
        fpr_list.append(fpr)

        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_threshold = t

    # Compute AUC using trapezoidal rule
    fpr_arr = np.array(fpr_list)
    tpr_arr = np.array(tpr_list)
    sorted_indices = np.argsort(fpr_arr)
    fpr_sorted = fpr_arr[sorted_indices]
    tpr_sorted = tpr_arr[sorted_indices]
    auc = np.trapz(tpr_sorted, fpr_sorted)

    print(f"\n{'=' * 40}")
    print(f"  Optimal Threshold: {best_threshold:.6f}")
    print(f"  Best Accuracy:     {best_accuracy:.4f}")
    print(f"  AUC:               {auc:.4f}")
    print(f"{'=' * 40}")

    # Save plot
    if save_plot:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(1, 2, figsize=(14, 6))

            # Distribution plot
            axes[0].hist(live_ratios, bins=50, alpha=0.7, label='Live', color='#34D399')
            axes[0].hist(replay_ratios, bins=50, alpha=0.7, label='Replay', color='#F87171')
            axes[0].axvline(best_threshold, color='#8B5CF6', linestyle='--',
                           linewidth=2, label=f'Threshold={best_threshold:.4f}')
            axes[0].set_xlabel('HFE Ratio')
            axes[0].set_ylabel('Count')
            axes[0].set_title('HFE Distribution: Live vs Replay')
            axes[0].legend()

            # ROC curve
            axes[1].plot(fpr_sorted, tpr_sorted, color='#8B5CF6', linewidth=2)
            axes[1].plot([0, 1], [0, 1], 'k--', alpha=0.3)
            axes[1].set_xlabel('False Positive Rate')
            axes[1].set_ylabel('True Positive Rate')
            axes[1].set_title(f'ROC Curve (AUC = {auc:.4f})')
            axes[1].fill_between(fpr_sorted, tpr_sorted, alpha=0.1, color='#8B5CF6')

            plt.tight_layout()
            plot_path = "ml/models/liveness_calibration.png"
            os.makedirs(os.path.dirname(plot_path), exist_ok=True)
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"\n[Calibrate] ROC plot saved to: {plot_path}")
        except ImportError:
            print("[Calibrate] matplotlib not available — skipping plot.")

    return best_threshold, auc


if __name__ == "__main__":
    threshold, auc = calibrate(num_samples=200, save_plot=True)
    print(f"\n✅ Update architecture/config.yaml:")
    print(f"   speaker_verification.liveness_hfe_threshold: {threshold:.6f}")
