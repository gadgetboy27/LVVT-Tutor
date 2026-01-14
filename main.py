from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.core.database import engine, Base
from app.api.auth import router as auth_router
from app.api.standards import router as standards_router
from app.api.quiz import router as quiz_router
from app.api.learning import router as learning_router
from app.api.practice_exam import router as practice_exam_router
from app.api.spaced_repetition import router as spaced_repetition_router
from app.api.peer_comparison import router as peer_comparison_router
from app.api.mentor import router as mentor_router
from app.api.audio import router as audio_router
from app.api.offline import router as offline_router
from app.api.pdf_viewer import router as pdf_viewer_router

from app.models import enhanced

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LVV-Learn: LVV Certifier Training API",
    description="Production-ready API for LVV certification training with RAG-powered Q&A, quizzes, and section mastery tracking",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth_router)
app.include_router(standards_router)
app.include_router(quiz_router)
app.include_router(learning_router)
app.include_router(practice_exam_router)
app.include_router(spaced_repetition_router)
app.include_router(peer_comparison_router)
app.include_router(mentor_router)
app.include_router(audio_router)
app.include_router(offline_router)
app.include_router(pdf_viewer_router)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("quiz.html", {"request": request})


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
