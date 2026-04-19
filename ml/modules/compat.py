"""
Compatibility Patches
======================
Consolidated monkey-patches for library incompatibilities.

All patches are documented with the upstream issue and applied
once via apply_all_patches(). Import this module early in the
application lifecycle.

Patches:
  1. Whisper ffmpeg path   — Use imageio_ffmpeg's bundled binary on Windows
  2. HuggingFace Hub       — Map deprecated use_auth_token → token kwarg
  3. Windows symlink        — Fall back to file copy when lacking admin privileges
  4. SpeechBrain fetch      — Handle missing custom.py in pretrained models
"""

import os
import sys
import pathlib
import shutil
import numpy as np

_patches_applied = False


def _patch_whisper_ffmpeg():
    """
    Patch 1: Whisper ffmpeg path
    ----------------------------
    Whisper's load_audio() shells out to bare "ffmpeg" which fails on Windows
    if ffmpeg isn't on PATH. We redirect to imageio_ffmpeg's bundled binary.
    """
    try:
        import imageio_ffmpeg as iff
        ffmpeg_exe = iff.get_ffmpeg_exe()
    except ImportError:
        ffmpeg_exe = "ffmpeg"

    import subprocess as sp
    import whisper
    from whisper.audio import SAMPLE_RATE

    def patched_load_audio(file: str, sr: int = SAMPLE_RATE):
        cmd = [
            ffmpeg_exe, "-nostdin", "-threads", "0",
            "-i", file,
            "-f", "s16le", "-ac", "1",
            "-acodec", "pcm_s16le", "-ar", str(sr),
            "-",
        ]
        try:
            out = sp.run(cmd, capture_output=True, check=True).stdout
        except sp.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to load audio: {e.stderr.decode()}"
            ) from e
        return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0

    whisper.audio.load_audio = patched_load_audio
    whisper.load_audio = patched_load_audio


def _patch_huggingface_hub():
    """
    Patch 2: HuggingFace Hub use_auth_token → token
    -------------------------------------------------
    SpeechBrain 1.0.0 passes the deprecated `use_auth_token` kwarg to
    huggingface_hub.hf_hub_download(). Newer versions of huggingface_hub
    renamed it to `token` and raise on the old name.
    """
    import huggingface_hub
    original = huggingface_hub.hf_hub_download

    def patched(*args, **kwargs):
        if "use_auth_token" in kwargs:
            kwargs["token"] = kwargs.pop("use_auth_token")
        return original(*args, **kwargs)

    huggingface_hub.hf_hub_download = patched


def _patch_windows_symlink():
    """
    Patch 3: Windows symlink privilege bypass
    -------------------------------------------
    Creating symlinks on Windows requires admin privileges (winerror 1314).
    Fall back to a hard copy when the privilege isn't available.
    """
    original = pathlib.Path.symlink_to

    def patched(self, target, target_is_directory=False):
        try:
            original(self, target, target_is_directory)
        except OSError as e:
            if getattr(e, "winerror", None) == 1314:
                if target_is_directory or os.path.isdir(str(target)):
                    shutil.copytree(str(target), str(self))
                else:
                    shutil.copy2(str(target), str(self))
            else:
                raise

    pathlib.Path.symlink_to = patched


def _patch_speechbrain_fetch():
    """
    Patch 4: SpeechBrain missing custom.py
    ----------------------------------------
    Some pretrained models don't ship a custom.py, causing a 404
    during fetch. We catch that and create a dummy file.
    """
    import speechbrain.utils.fetching
    original = speechbrain.utils.fetching.fetch

    def patched(filename, source, savedir="./pretrained_model_checkpoints",
                *args, **kwargs):
        try:
            return original(filename, source, savedir=savedir, *args, **kwargs)
        except Exception as e:
            if "custom.py" in filename and (
                "404" in str(e) or "Entry Not Found" in str(e)
            ):
                print(f"[Compat] Ignored missing {filename} from {source}.")
                dummy_path = os.path.join(savedir, filename)
                os.makedirs(savedir, exist_ok=True)
                with open(dummy_path, "w") as f:
                    f.write("# dummy custom.py\n")
                return pathlib.Path(dummy_path)
            raise

    speechbrain.utils.fetching.fetch = patched


def apply_all_patches():
    """Apply all compatibility patches (idempotent — safe to call multiple times)."""
    global _patches_applied
    if _patches_applied:
        return

    _patch_whisper_ffmpeg()
    _patch_huggingface_hub()
    _patch_windows_symlink()
    _patch_speechbrain_fetch()

    _patches_applied = True
    print("[Compat] All compatibility patches applied.")
