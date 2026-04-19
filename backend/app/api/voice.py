"""
Voice Processing API Routes
=============================
Endpoints for voice command processing and speaker enrollment.
"""

import os
import uuid
import shutil
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import User, SpeakerProfile
from backend.app.services.pipeline import PipelineOrchestrator
from backend.app.utils.audio_utils import convert_to_wav

router = APIRouter(prefix="/voice", tags=["Voice Processing"])


def get_app_state():
    """Get app state from main module."""
    from backend.app.main import app_state
    return app_state


def _get_current_user_from_token(token: str, db: Session):
    """Extract user from JWT token. Returns None if no auth configured yet."""
    try:
        from backend.app.core.security import decode_access_token
        payload = decode_access_token(token)
        user = db.query(User).filter_by(username=payload["username"]).first()
        return user
    except Exception:
        return None


@router.post("/process")
async def process_voice_command(
    audio: UploadFile = File(...),
    user_id: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Process a voice command through the full ML pipeline.

    Flow: Audio → STT → Speaker Verification → Intent → Fraud → Auth

    Returns pipeline results with auth decision.
    If auth passes, frontend should proceed to PIN entry and then payment.
    """
    app_state = get_app_state()

    # Validate user
    user = db.query(User).filter_by(username=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")

    # Save uploaded audio to temp file (browser sends WebM)
    audio_dir = "storage/audio"
    os.makedirs(audio_dir, exist_ok=True)
    unique_id = uuid.uuid4().hex[:8]
    webm_path = os.path.join(audio_dir, f"{user_id}_{unique_id}.webm")
    wav_path = os.path.join(audio_dir, f"{user_id}_{unique_id}.wav")

    try:
        # Save raw upload
        with open(webm_path, "wb") as f:
            content = await audio.read()
            f.write(content)

        # Convert to WAV for Whisper/SpeechBrain
        convert_to_wav(webm_path, wav_path)

        # Run pipeline
        orchestrator = PipelineOrchestrator(app_state)
        result = await orchestrator.process_voice_command(
            audio_path=wav_path,
            user_id=user_id,
            db_user_id=user.id,
            db=db,
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")
    finally:
        # Cleanup temp audio files
        for path in [webm_path, wav_path]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass


@router.post("/process-stream")
async def process_voice_command_stream(
    audio: UploadFile = File(...),
    user_id: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Process a voice command with Server-Sent Events (SSE) streaming.
    Each pipeline stage result is emitted as it completes.
    """
    app_state = get_app_state()

    # Validate user
    user = db.query(User).filter_by(username=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")

    # Save + convert audio
    audio_dir = "storage/audio"
    os.makedirs(audio_dir, exist_ok=True)
    unique_id = uuid.uuid4().hex[:8]
    webm_path = os.path.join(audio_dir, f"{user_id}_{unique_id}.webm")
    wav_path = os.path.join(audio_dir, f"{user_id}_{unique_id}.wav")

    with open(webm_path, "wb") as f:
        content = await audio.read()
        f.write(content)

    try:
        convert_to_wav(webm_path, wav_path)
    except Exception as e:
        # Cleanup on conversion failure
        for p in [webm_path, wav_path]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        raise HTTPException(status_code=400, detail=f"Audio conversion failed: {e}")

    orchestrator = PipelineOrchestrator(app_state)

    async def event_generator():
        try:
            async for event in orchestrator.process_voice_command_streaming(
                audio_path=wav_path,
                user_id=user_id,
                db_user_id=user.id,
                db=db,
            ):
                yield event
        finally:
            for path in [webm_path, wav_path]:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/process-text")
async def process_text_command(
    text: str = Form(...),
    user_id: str = Form(...),
    sv_override: bool = Form(default=True),
    db: Session = Depends(get_db),
):
    """
    Process a text command (skips STT, optionally skips SV).
    Useful for testing the pipeline without audio input.

    Set sv_override=true to bypass speaker verification for text commands.
    """
    app_state = get_app_state()

    # Validate user
    user = db.query(User).filter_by(username=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    # Run text pipeline
    orchestrator = PipelineOrchestrator(app_state)
    result = orchestrator.process_text_command(
        text=text,
        user_id=user_id,
        db_user_id=user.id,
        db=db,
        sv_override=sv_override,
    )

    return result


@router.post("/enroll")
async def enroll_speaker(
    user_id: str = Form(...),
    audio_files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Enroll a speaker's voice profile for verification.
    Requires at least 3 audio samples.
    """
    app_state = get_app_state()

    # Validate user
    user = db.query(User).filter_by(username=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    if len(audio_files) < 3:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 3 audio samples for enrollment. Got {len(audio_files)}."
        )

    # Save and convert audio files
    audio_dir = f"storage/audio/enrollment_{user_id}"
    os.makedirs(audio_dir, exist_ok=True)

    audio_paths = []
    for i, audio in enumerate(audio_files):
        webm_path = os.path.join(audio_dir, f"enroll_{i}.webm")
        wav_path = os.path.join(audio_dir, f"enroll_{i}.wav")
        with open(webm_path, "wb") as f:
            content = await audio.read()
            f.write(content)
        try:
            convert_to_wav(webm_path, wav_path)
            audio_paths.append(wav_path)
        except Exception:
            # If conversion fails, try using raw file directly
            audio_paths.append(webm_path)

    try:
        # Load SV model if needed
        if app_state.get("speaker_verification") is None:
            from ml.modules.speaker_verification import SpeakerVerification
            sv = SpeakerVerification(config_path="architecture/config.yaml")
            sv.load_model()
            app_state["speaker_verification"] = sv

        sv = app_state["speaker_verification"]
        result = sv.enroll_speaker(user_id, audio_paths, authenticated_user_id=user_id)

        # Update speaker profile in DB
        profile = db.query(SpeakerProfile).filter_by(user_id=user.id).first()
        if profile:
            profile.embedding_path = result["profile_path"]
            profile.num_enrollment_samples = result["num_samples"]
            profile.is_enrolled = True
            import datetime
            profile.enrolled_at = datetime.datetime.utcnow()
        else:
            profile = SpeakerProfile(
                user_id=user.id,
                embedding_path=result["profile_path"],
                num_enrollment_samples=result["num_samples"],
                is_enrolled=True,
            )
            import datetime
            profile.enrolled_at = datetime.datetime.utcnow()
            db.add(profile)

        db.commit()

        return {
            "success": True,
            "speaker_id": user_id,
            "num_samples": result["num_samples"],
            "message": f"Speaker '{user_id}' enrolled successfully with {result['num_samples']} samples.",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enrollment failed: {str(e)}")
    finally:
        # Cleanup enrollment audio files
        if os.path.exists(audio_dir):
            shutil.rmtree(audio_dir)


@router.post("/verify")
async def verify_speaker_step_up(
    audio: UploadFile = File(...),
    user_id: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Verify the speaker's voice for step-up authentication.
    """
    app_state = get_app_state()

    # Validate user
    user = db.query(User).filter_by(username=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    # Save and convert audio
    audio_dir = "storage/audio/verify_stepup"
    os.makedirs(audio_dir, exist_ok=True)
    unique_id = uuid.uuid4().hex[:8]
    webm_path = os.path.join(audio_dir, f"verify_{user_id}_{unique_id}.webm")
    wav_path = os.path.join(audio_dir, f"verify_{user_id}_{unique_id}.wav")

    try:
        with open(webm_path, "wb") as f:
            content = await audio.read()
            f.write(content)

        convert_to_wav(webm_path, wav_path)

        # Load SV model if needed
        if app_state.get("speaker_verification") is None:
            from ml.modules.speaker_verification import SpeakerVerification
            sv = SpeakerVerification(config_path="architecture/config.yaml")
            sv.load_model()
            app_state["speaker_verification"] = sv

        sv = app_state["speaker_verification"]
        result = sv.verify_speaker(user_id, wav_path, authenticated_user_id=user_id)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
    finally:
        for path in [webm_path, wav_path]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
