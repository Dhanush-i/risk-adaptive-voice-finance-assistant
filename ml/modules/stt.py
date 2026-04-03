"""
Speech-to-Text Module — Whisper Wrapper
========================================
Converts audio input to text using OpenAI's Whisper model.

Input:  Audio file path (16kHz mono WAV)
Output: { "transcript": str, "language": str, "confidence": float }
"""

import os
import yaml
import whisper
import numpy as np
import torch
from typing import Dict, Any, Optional

# --- Monkey-patch Whisper to use bundled FFmpeg from imageio_ffmpeg ---
# Whisper's load_audio() calls bare "ffmpeg" which fails on Windows if
# ffmpeg is not on the system PATH.  We replace the command with the
# absolute path that imageio_ffmpeg ships.
try:
    import imageio_ffmpeg as _iff
    _FFMPEG_EXE = _iff.get_ffmpeg_exe()
except ImportError:
    _FFMPEG_EXE = "ffmpeg"  # fallback – hope it's on PATH

import subprocess as _sp
from whisper.audio import SAMPLE_RATE as _SR

def _patched_load_audio(file: str, sr: int = _SR):
    """Load audio via the bundled ffmpeg binary."""
    cmd = [
        _FFMPEG_EXE,
        "-nostdin",
        "-threads", "0",
        "-i", file,
        "-f", "s16le",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        "-ar", str(sr),
        "-",
    ]
    try:
        out = _sp.run(cmd, capture_output=True, check=True).stdout
    except _sp.CalledProcessError as e:
        raise RuntimeError(f"Failed to load audio: {e.stderr.decode()}") from e

    return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0

# Apply the patch
whisper.audio.load_audio = _patched_load_audio
whisper.load_audio = _patched_load_audio


class SpeechToText:
    """Wrapper around OpenAI Whisper for speech-to-text transcription."""

    def __init__(self, config_path: str = "architecture/config.yaml"):
        """
        Initialize the STT module.

        Args:
            config_path: Path to the project configuration file.
        """
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        stt_config = config["stt"]
        self.model_name = stt_config["model_name"]
        self.language = stt_config["language"]
        self.device = stt_config["device"]
        self.sample_rate = stt_config["audio_sample_rate"]
        self.max_duration = stt_config["max_audio_duration_sec"]

        self.model = None

    def load_model(self) -> None:
        """Load the Whisper model into memory."""
        print(f"[STT] Loading Whisper model '{self.model_name}' on {self.device}...")
        self.model = whisper.load_model(self.model_name, device=self.device)
        print(f"[STT] Model loaded successfully.")

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        """
        Transcribe an audio file to text.

        Args:
            audio_path: Path to the audio file (WAV, MP3, etc.)

        Returns:
            Dictionary with transcript, language, and confidence score.

        Raises:
            FileNotFoundError: If the audio file doesn't exist.
            RuntimeError: If the model hasn't been loaded.
        """
        if self.model is None:
            raise RuntimeError("[STT] Model not loaded. Call load_model() first.")

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"[STT] Audio file not found: {audio_path}")

        print(f"[STT] Transcribing: {audio_path}")

        # Transcribe with Whisper
        result = self.model.transcribe(
            audio_path,
            language=self.language,
            fp16=(self.device == "cuda"),
        )

        # Extract confidence from segments
        segments = result.get("segments", [])
        if segments:
            # Average the no_speech_prob across segments to estimate confidence
            # Lower no_speech_prob = higher confidence
            avg_no_speech = np.mean([s.get("no_speech_prob", 0.0) for s in segments])
            confidence = round(1.0 - avg_no_speech, 4)

            # Also consider avg_logprob for a more nuanced confidence
            avg_logprob = np.mean([s.get("avg_logprob", -1.0) for s in segments])
            # Convert logprob to probability (clamped)
            logprob_confidence = round(min(1.0, np.exp(avg_logprob)), 4)

            # Combine both signals
            confidence = round((confidence + logprob_confidence) / 2, 4)
        else:
            confidence = 0.0

        output = {
            "transcript": result["text"].strip(),
            "language": result.get("language", self.language),
            "confidence": confidence,
        }

        print(f"[STT] Result: '{output['transcript']}' (confidence: {output['confidence']})")
        return output

    def transcribe_audio_array(self, audio_array: np.ndarray) -> Dict[str, Any]:
        """
        Transcribe from a numpy audio array (16kHz float32).

        Args:
            audio_array: Numpy array of audio samples (float32, 16kHz).

        Returns:
            Dictionary with transcript, language, and confidence score.
        """
        if self.model is None:
            raise RuntimeError("[STT] Model not loaded. Call load_model() first.")

        # Ensure correct dtype
        audio = audio_array.astype(np.float32)

        # Pad/trim to 30 seconds as Whisper expects
        audio = whisper.pad_or_trim(audio)

        # Make log-Mel spectrogram
        mel = whisper.log_mel_spectrogram(audio).to(self.device)

        # Detect language (optional, since we specify it)
        _, probs = self.model.detect_language(mel)
        detected_lang = max(probs, key=probs.get)

        # Decode
        options = whisper.DecodingOptions(language=self.language, fp16=(self.device == "cuda"))
        result = whisper.decode(self.model, mel, options)

        confidence = round(min(1.0, np.exp(result.avg_logprob)), 4) if result.avg_logprob else 0.5

        output = {
            "transcript": result.text.strip(),
            "language": detected_lang,
            "confidence": confidence,
        }

        print(f"[STT] Result: '{output['transcript']}' (confidence: {output['confidence']})")
        return output


# --- Standalone Test ---
if __name__ == "__main__":
    print("=" * 60)
    print("STT Module — Standalone Test")
    print("=" * 60)

    stt = SpeechToText()
    stt.load_model()

    # Test with a generated sine wave (should produce gibberish, but proves the pipeline works)
    import soundfile as sf

    test_audio_path = "storage/audio/test_stt.wav"
    os.makedirs("storage/audio", exist_ok=True)

    # Generate a 3-second audio with speech-like characteristics
    sr = 16000
    duration = 3
    t = np.linspace(0, duration, sr * duration, dtype=np.float32)
    # Simple sine wave — Whisper will try to transcribe it
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    sf.write(test_audio_path, audio, sr)
    print(f"\n[TEST] Generated test audio: {test_audio_path}")

    result = stt.transcribe(test_audio_path)
    print(f"\n[TEST] Transcription result:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # Cleanup
    os.remove(test_audio_path)
    print("\n[TEST] ✅ STT module test completed successfully!")
