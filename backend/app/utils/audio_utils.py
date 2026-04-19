"""
Audio Utilities — Format Conversion
=====================================
Converts browser-recorded audio (WebM/OGG) to 16kHz mono WAV
for consumption by Whisper and SpeechBrain.

Uses pydub with the imageio-ffmpeg binary so no system-wide
ffmpeg installation is required on Windows.
"""

import os
import tempfile
from typing import Optional


def _get_ffmpeg_path() -> str:
    """Get the ffmpeg binary path, preferring imageio_ffmpeg's bundled copy."""
    try:
        import imageio_ffmpeg as iff
        return iff.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"  # Fall back to system PATH


def convert_to_wav(
    input_path: str,
    output_path: Optional[str] = None,
    sample_rate: int = 16000,
    channels: int = 1,
) -> str:
    """
    Convert any audio file to 16kHz mono WAV using subprocess to ffmpeg directly.
    """
    import subprocess
    
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Audio file not found: {input_path}")

    if output_path is None:
        base, _ = os.path.splitext(input_path)
        output_path = base + ".wav"

    ffmpeg_path = _get_ffmpeg_path()

    cmd = [
        ffmpeg_path,
        "-y",               # Overwrite existing
        "-i", input_path,   # Input file
        "-ar", str(sample_rate),
        "-ac", str(channels),
        output_path
    ]

    try:
        # Hide output window and suppress console output
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )
        print(f"[Audio] Converted {input_path} → {output_path} ({sample_rate}Hz, {channels}ch)")
        return output_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Audio conversion failed for '{input_path}' using ffmpeg. Error: {e}") from e
