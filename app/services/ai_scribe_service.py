# app/services/ai_scribe_service.py
from sqlalchemy.orm import Session
from typing import Optional
from app.models.all_models import AiScribeJob
from app.core.enums import AiScribeJobStatus

class AiScribeService:
    def __init__(self, db: Session):
        self.db = db

    def start_transcription(self, consultation_id: int, clinician_id: int, audio_s3_key: str) -> AiScribeJob:
        """Initializes a new background Ambient AI Scribe job for an audio file."""
        job = AiScribeJob(
            consultation_id=consultation_id,
            clinician_staff_id=clinician_id,
            audio_s3_key=audio_s3_key,
            status=AiScribeJobStatus.PENDING
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        # In a real-world scenario, we would enqueue a message to Redis/Celery 
        # or an AWS SQS queue to trigger an LLM (like OpenAI Whisper API) 
        # to download the S3 audio, transcribe it, and generate the SOAP note.
        # queue_service.enqueue("ai_transcription_worker", job_id=job.id)
        
        return job

    def get_job_status(self, consultation_id: int) -> Optional[AiScribeJob]:
        """Fetches the transcription job associated with a given consultation."""
        return self.db.query(AiScribeJob).filter(AiScribeJob.consultation_id == consultation_id).first()
