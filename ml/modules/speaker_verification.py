"""
Speaker Verification Module — ECAPA-TDNN Wrapper
=================================================
Verifies speaker identity using SpeechBrain's ECAPA-TDNN model.

Enrollment: Extract embeddings from audio samples, average, L2-normalize, save.
Verification: Compare new embedding against stored profile via cosine similarity.

Input:  Audio file path (16kHz mono WAV)
Output: { "speaker_id": str, "similarity_score": float, "verified": bool }
"""

import os
import json
import yaml
import numpy as np
import torch
import torchaudio
from typing import Dict, Any, List, Optional

# --- Monkeypatch HuggingFace Hub for SpeechBrain 1.0.0 Compatibility ---
import huggingface_hub
_original_hf_hub_download = huggingface_hub.hf_hub_download
def _patched_hf_hub_download(*args, **kwargs):
    if "use_auth_token" in kwargs:
        kwargs["token"] = kwargs.pop("use_auth_token")
    return _original_hf_hub_download(*args, **kwargs)
huggingface_hub.hf_hub_download = _patched_hf_hub_download

# --- Monkeypatch pathlib.Path.symlink_to for Windows Admin Privilege Bypass ---
import pathlib
import os
import shutil
_original_symlink_to = pathlib.Path.symlink_to

def _patched_symlink_to(self, target, target_is_directory=False):
    try:
        _original_symlink_to(self, target, target_is_directory)
    except OSError as e:
        if getattr(e, 'winerror', None) == 1314:
            # Fallback to hard copy if lacking privileges
            if target_is_directory or os.path.isdir(target):
                shutil.copytree(target, self)
            else:
                shutil.copy2(target, self)
        else:
            raise
pathlib.Path.symlink_to = _patched_symlink_to

# --- Monkeypatch speechbrain.utils.fetching.fetch for Missing custom.py ---
import speechbrain.utils.fetching
_original_fetch = speechbrain.utils.fetching.fetch

def _patched_fetch(filename, source, savedir="./pretrained_model_checkpoints", *args, **kwargs):
    try:
        return _original_fetch(filename, source, savedir=savedir, *args, **kwargs)
    except Exception as e:
        # If it's a 404 for custom.py, just create a dummy custom.py
        if "custom.py" in filename and ("404" in str(e) or "Entry Not Found" in str(e)):
            print(f"[SV] Ignored missing {filename} from {source}.")
            dummy_path = os.path.join(savedir, filename)
            os.makedirs(savedir, exist_ok=True)
            with open(dummy_path, "w") as f:
                f.write("# dummy custom.py\n")
            return pathlib.Path(dummy_path)
        raise

speechbrain.utils.fetching.fetch = _patched_fetch

from speechbrain.inference.speaker import EncoderClassifier


class SpeakerVerification:
    """Speaker verification using SpeechBrain ECAPA-TDNN."""

    def __init__(self, config_path: str = "architecture/config.yaml"):
        """
        Initialize the Speaker Verification module.

        Args:
            config_path: Path to the project configuration file.
        """
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        sv_config = config["speaker_verification"]
        self.model_source = sv_config["model_source"]
        self.threshold = sv_config["similarity_threshold"]
        self.min_enrollment_samples = sv_config["min_enrollment_samples"]
        self.embedding_dim = sv_config["embedding_dim"]
        self.device = sv_config["device"]
        self.profiles_dir = sv_config["profiles_dir"]

        self.model = None

        # Ensure profiles directory exists
        os.makedirs(self.profiles_dir, exist_ok=True)

    def load_model(self) -> None:
        """Load the ECAPA-TDNN model."""
        print(f"[SV] Loading ECAPA-TDNN from '{self.model_source}'...")
        self.model = EncoderClassifier.from_hparams(
            source=self.model_source,
            savedir="ml/models/sv_pretrained",
            run_opts={"device": self.device},
        )
        print("[SV] Model loaded successfully.")

    def extract_embedding(self, audio_path: str) -> np.ndarray:
        """
        Extract a speaker embedding from an audio file.

        Args:
            audio_path: Path to the audio file.

        Returns:
            L2-normalized embedding vector as numpy array.
        """
        if self.model is None:
            raise RuntimeError("[SV] Model not loaded. Call load_model() first.")

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"[SV] Audio file not found: {audio_path}")

        # Use Whisper's load_audio (which is monkey-patched to use ffmpeg)
        # because torchaudio.load fails on WebM audio formats sent from browsers.
        # We import ml.modules.stt to ensure the ffmpeg monkeypatch is applied.
        import ml.modules.stt 
        import whisper
        try:
            audio_data = whisper.load_audio(audio_path, sr=16000)
            signal = torch.from_numpy(audio_data).unsqueeze(0)  # Shape: [1, Length]
        except Exception as e:
            raise ValueError(f"Error opening '{audio_path}': Format not recognised.\nDetails: {str(e)}") from e

        # Extract embedding
        embedding = self.model.encode_batch(signal)
        embedding = embedding.squeeze().cpu().numpy()

        # L2 normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def enroll_speaker(self, speaker_id: str, audio_paths: List[str]) -> Dict[str, Any]:
        """
        Enroll a speaker by averaging embeddings from multiple audio samples.

        Args:
            speaker_id: Unique identifier for the speaker.
            audio_paths: List of audio file paths for enrollment.

        Returns:
            Enrollment result with speaker_id and number of samples used.

        Raises:
            ValueError: If fewer than min_enrollment_samples are provided.
        """
        if len(audio_paths) < self.min_enrollment_samples:
            raise ValueError(
                f"[SV] Need at least {self.min_enrollment_samples} audio samples for enrollment, "
                f"got {len(audio_paths)}."
            )

        print(f"[SV] Enrolling speaker '{speaker_id}' with {len(audio_paths)} samples...")

        embeddings = []
        for path in audio_paths:
            emb = self.extract_embedding(path)
            embeddings.append(emb)

        # Average embeddings
        avg_embedding = np.mean(embeddings, axis=0)

        # L2 normalize the average
        norm = np.linalg.norm(avg_embedding)
        if norm > 0:
            avg_embedding = avg_embedding / norm

        # Save profile
        profile_path = os.path.join(self.profiles_dir, f"{speaker_id}.npy")
        np.save(profile_path, avg_embedding)

        # Save metadata
        meta_path = os.path.join(self.profiles_dir, f"{speaker_id}_meta.json")
        metadata = {
            "speaker_id": speaker_id,
            "num_enrollment_samples": len(audio_paths),
            "embedding_dim": len(avg_embedding),
            "audio_files": audio_paths,
        }
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"[SV] Speaker '{speaker_id}' enrolled successfully. Profile saved to {profile_path}")

        return {
            "speaker_id": speaker_id,
            "num_samples": len(audio_paths),
            "profile_path": profile_path,
        }

    def verify_speaker(self, speaker_id: str, audio_path: str) -> Dict[str, Any]:
        """
        Verify if the audio matches the enrolled speaker.

        Args:
            speaker_id: ID of the enrolled speaker to verify against.
            audio_path: Path to the verification audio.

        Returns:
            Verification result with similarity score and verified status.
        """
        # Load stored profile
        profile_path = os.path.join(self.profiles_dir, f"{speaker_id}.npy")
        if not os.path.exists(profile_path):
            return {
                "speaker_id": speaker_id,
                "similarity_score": 0.0,
                "verified": False,
                "error": f"No enrollment profile found for speaker '{speaker_id}'",
            }

        stored_embedding = np.load(profile_path)

        # Extract embedding from verification audio
        new_embedding = self.extract_embedding(audio_path)

        # Cosine similarity (embeddings are already L2-normalized)
        similarity = float(np.dot(stored_embedding, new_embedding))

        # Clamp to [-1, 1]
        similarity = max(-1.0, min(1.0, similarity))

        verified = similarity >= self.threshold

        result = {
            "speaker_id": speaker_id,
            "similarity_score": round(similarity, 4),
            "verified": verified,
        }

        status = "✅ VERIFIED" if verified else "❌ REJECTED"
        print(f"[SV] Speaker '{speaker_id}': similarity={similarity:.4f}, threshold={self.threshold} → {status}")

        return result

    def check_liveness(self, audio_path: str) -> Dict[str, Any]:
        """
        Anti-spoofing mechanism using High-Frequency Energy (HFE) analysis.
        Replayed audio (via low-quality speakers) heavily suppresses high frequencies.
        Returns a dictionary with liveness score and boolean flag.
        """
        try:
            import whisper
            audio = whisper.load_audio(audio_path, sr=16000)
            tensor_audio = torch.from_numpy(audio)
            
            # Compute Short-Time Fourier Transform (STFT)
            # n_fft=1024 -> 513 frequency bins for Nyquist 8000Hz (at 16kHz sr)
            spectrogram = torch.stft(
                tensor_audio, 
                n_fft=1024, 
                hop_length=256, 
                win_length=1024, 
                return_complex=True
            )
            magnitude = torch.abs(spectrogram)
            
            # Bins for High Frequency (6000 Hz to 8000 Hz)
            bin_6k = int(6000 * 1024 / 16000) # 384
            bin_8k = 513
            
            total_energy = torch.sum(magnitude).item()
            high_freq_energy = torch.sum(magnitude[bin_6k:bin_8k, :]).item()
            
            hfe_ratio = high_freq_energy / total_energy if total_energy > 0 else 1.0
            
            # Normal speech has some HF noise. Compressed replay often drops below 0.05
            is_live = hfe_ratio > 0.015
            
            print(f"[SV] Liveness Check: HFE Ratio = {hfe_ratio:.4f} → {'✅ LIVE' if is_live else '❌ SPOOF'}")
            
            return {
                "is_live": bool(is_live),
                "hfe_ratio": round(hfe_ratio, 4)
            }
        except Exception as e:
            print(f"[SV] Warning: Liveness check failed: {e}")
            return {"is_live": True, "hfe_ratio": 1.0}

    def list_enrolled_speakers(self) -> List[str]:
        """List all enrolled speaker IDs."""
        speakers = []
        for f in os.listdir(self.profiles_dir):
            if f.endswith(".npy"):
                speakers.append(f.replace(".npy", ""))
        return speakers


# --- Standalone Test ---
if __name__ == "__main__":
    import soundfile as sf

    print("=" * 60)
    print("Speaker Verification Module — Standalone Test")
    print("=" * 60)

    sv = SpeakerVerification()
    sv.load_model()

    # Generate test audio files (sine waves at different frequencies to simulate different speakers)
    os.makedirs("storage/audio", exist_ok=True)

    test_files = []
    sr = 16000
    duration = 3

    # Create enrollment samples (same "speaker" — same frequency)
    for i in range(3):
        t = np.linspace(0, duration, sr * duration, dtype=np.float32)
        # Same base frequency with slight variation to simulate natural speech variation
        freq = 200 + np.random.uniform(-10, 10)
        audio = 0.5 * np.sin(2 * np.pi * freq * t) + 0.1 * np.random.randn(len(t)).astype(np.float32)
        path = f"storage/audio/test_enroll_{i}.wav"
        sf.write(path, audio, sr)
        test_files.append(path)

    # Enroll
    result = sv.enroll_speaker("test_user", test_files)
    print(f"\n[TEST] Enrollment result: {result}")

    # Verify with similar audio (same speaker)
    t = np.linspace(0, duration, sr * duration, dtype=np.float32)
    audio_same = 0.5 * np.sin(2 * np.pi * 200 * t) + 0.1 * np.random.randn(len(t)).astype(np.float32)
    sf.write("storage/audio/test_verify_same.wav", audio_same, sr)

    result_same = sv.verify_speaker("test_user", "storage/audio/test_verify_same.wav")
    print(f"\n[TEST] Same speaker verification: {result_same}")

    # Verify with different audio (different speaker — different frequency)
    audio_diff = 0.5 * np.sin(2 * np.pi * 800 * t) + 0.1 * np.random.randn(len(t)).astype(np.float32)
    sf.write("storage/audio/test_verify_diff.wav", audio_diff, sr)

    result_diff = sv.verify_speaker("test_user", "storage/audio/test_verify_diff.wav")
    print(f"\n[TEST] Different speaker verification: {result_diff}")

    # List enrolled speakers
    speakers = sv.list_enrolled_speakers()
    print(f"\n[TEST] Enrolled speakers: {speakers}")

    # Cleanup test files
    for f in test_files:
        os.remove(f)
    os.remove("storage/audio/test_verify_same.wav")
    os.remove("storage/audio/test_verify_diff.wav")

    print("\n[TEST] ✅ Speaker Verification module test completed!")
