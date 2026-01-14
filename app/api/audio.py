from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import hashlib
import os
from app.core.database import get_db
from app.models.enhanced import AudioCache
from app.services.rag.vector_store import get_chroma_client, get_or_create_collection
from openai import OpenAI

router = APIRouter(prefix="/api/audio", tags=["Audio Study Mode"])

AUDIO_CACHE_DIR = "audio_cache"
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)


class TextToSpeechRequest(BaseModel):
    text: str
    voice: str = "alloy"
    speed: float = 1.0


class StandardAudioRequest(BaseModel):
    standard_number: str
    section_index: Optional[int] = None
    voice: str = "alloy"


def get_openai_client():
    base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
    api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
    
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API not configured")
    
    return OpenAI(base_url=base_url, api_key=api_key)


@router.post("/synthesize")
async def synthesize_speech(
    request: TextToSpeechRequest,
    db: Session = Depends(get_db)
):
    text_hash = hashlib.md5(f"{request.text}:{request.voice}".encode()).hexdigest()
    
    cached = db.query(AudioCache).filter(AudioCache.content_hash == text_hash).first()
    
    if cached and os.path.exists(cached.audio_file_path):
        cached.access_count += 1
        db.commit()
        return {"audio_url": f"/api/audio/file/{text_hash}", "cached": True}
    
    try:
        client = get_openai_client()
        
        response = client.audio.speech.create(
            model="gpt-audio-mini",
            voice=request.voice,
            input=request.text[:4096],
            speed=request.speed
        )
        
        file_path = os.path.join(AUDIO_CACHE_DIR, f"{text_hash}.mp3")
        response.stream_to_file(file_path)
        
        audio_entry = AudioCache(
            content_hash=text_hash,
            text_preview=request.text[:500],
            audio_file_path=file_path
        )
        db.add(audio_entry)
        db.commit()
        
        return {"audio_url": f"/api/audio/file/{text_hash}", "cached": False}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio synthesis failed: {str(e)}")


@router.post("/standard")
async def synthesize_standard_audio(
    request: StandardAudioRequest,
    db: Session = Depends(get_db)
):
    try:
        chroma_client = get_chroma_client()
        collection = get_or_create_collection(chroma_client)
        
        results = collection.get(
            where={"standard_number": request.standard_number},
            include=["documents"]
        )
        
        if not results or not results.get('documents'):
            raise HTTPException(status_code=404, detail="Standard not found")
        
        chunks = results['documents']
        
        if request.section_index is not None:
            if request.section_index >= len(chunks):
                raise HTTPException(status_code=400, detail="Section index out of range")
            text = chunks[request.section_index]
        else:
            text = "\n\n".join(chunks[:3])
        
        text = text[:4000]
        
        synth_request = TextToSpeechRequest(text=text, voice=request.voice)
        return await synthesize_speech(synth_request, db)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file/{audio_hash}")
async def get_audio_file(
    audio_hash: str,
    db: Session = Depends(get_db)
):
    cached = db.query(AudioCache).filter(AudioCache.content_hash == audio_hash).first()
    
    if not cached or not os.path.exists(cached.audio_file_path):
        raise HTTPException(status_code=404, detail="Audio not found")
    
    cached.access_count += 1
    db.commit()
    
    return FileResponse(
        cached.audio_file_path,
        media_type="audio/mpeg",
        filename=f"study_audio_{audio_hash[:8]}.mp3"
    )


@router.get("/available/{standard_number}")
async def get_available_audio_sections(
    standard_number: str,
    db: Session = Depends(get_db)
):
    try:
        chroma_client = get_chroma_client()
        collection = get_or_create_collection(chroma_client)
        
        results = collection.get(
            where={"standard_number": standard_number},
            include=["documents"]
        )
        
        if not results or not results.get('documents'):
            return {"sections": [], "total": 0}
        
        sections = []
        for i, chunk in enumerate(results['documents']):
            preview = chunk[:100] + "..." if len(chunk) > 100 else chunk
            sections.append({
                "index": i,
                "preview": preview,
                "char_count": len(chunk)
            })
        
        return {"sections": sections, "total": len(sections)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
