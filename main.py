from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import time
from app.core.database import engine, Base, SessionLocal
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
from app.api.analytics import router as analytics_router
from app.models.quiz import Standard

from app.models import enhanced, analytics

Base.metadata.create_all(bind=engine)


def seed_initial_standards():
    db = SessionLocal()
    try:
        count = db.query(Standard).count()
        if count == 0:
            print("Seeding initial LVVTA standards...")
            initial_standards = [
                {"standard_number": "LVVTA_STD_Brakes", "title": "Brakes", "category": "Brakes", "summary": "LVVTA standard covering braking systems"},
                {"standard_number": "LVVTA_STD_Body_&_Chassis", "title": "Body & Chassis", "category": "Body & Structure", "summary": "LVVTA standard covering body and chassis modifications"},
                {"standard_number": "LVVTA_STD_Engine_&_Drivetrain", "title": "Engine & Drivetrain", "category": "Engine & Drivetrain", "summary": "LVVTA standard covering engine and drivetrain"},
                {"standard_number": "LVVTA_STD_Exhaust", "title": "Exhaust", "category": "Exhaust & Emissions", "summary": "LVVTA standard covering exhaust systems"},
                {"standard_number": "LVVTA_STD_Fuel_Systems", "title": "Fuel Systems", "category": "Fuel Systems", "summary": "LVVTA standard covering fuel systems"},
                {"standard_number": "LVVTA_STD_Lighting", "title": "Lighting", "category": "Lighting & Electrical", "summary": "LVVTA standard covering lighting and electrical"},
                {"standard_number": "LVVTA_STD_Suspension", "title": "Suspension", "category": "Suspension & Steering", "summary": "LVVTA standard covering suspension and steering"},
                {"standard_number": "LVVTA_STD_Wheels_&_Tyres", "title": "Wheels & Tyres", "category": "Wheels & Tyres", "summary": "LVVTA standard covering wheels and tyres"},
                {"standard_number": "ORS_Chapter_3", "title": "ORS Chapter 3 - Certification Categories", "category": "Certification Process", "summary": "LVV Certification categories and requirements"},
                {"standard_number": "ORS_Chapter_4", "title": "ORS Chapter 4 - Certifier Criteria", "category": "Certification Process", "summary": "LVV Certifier background criteria"},
                {"standard_number": "ORS_Chapter_5", "title": "ORS Chapter 5 - Application Process", "category": "Certification Process", "summary": "LVV Certifier application and appointment"},
                {"standard_number": "LVVTA_General_Compliance", "title": "General Compliance Overview", "category": "General Compliance", "summary": "General compliance requirements for LVV certification"},
            ]
            for std_data in initial_standards:
                std = Standard(**std_data)
                db.add(std)
            db.commit()
            print(f"Seeded {len(initial_standards)} initial standards")
        else:
            print(f"Database has {count} standards - skipping seed")
    except Exception as e:
        print(f"Error seeding standards: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_initial_standards()
    yield

app = FastAPI(
    title="LVV-Learn: LVV Certifier Training API",
    description="Production-ready API for LVV certification training with RAG-powered Q&A, quizzes, and section mastery tracking",
    version="1.0.0",
    lifespan=lifespan
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
app.include_router(analytics_router)


@app.middleware("http")
async def track_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/analytics"):
        try:
            db = SessionLocal()
            process_time = (time.time() - start_time) * 1000
            
            user_agent = request.headers.get("user-agent", "").lower()
            device = "mobile" if any(x in user_agent for x in ["mobile", "android", "iphone"]) else "desktop"
            
            event_type = "api_call"
            path = request.url.path
            if "/quiz/" in path:
                event_type = "quiz_generate" if "generate" in path else "quiz_action"
            elif "/standards/content" in path:
                event_type = "document_view"
            elif "/audio/" in path:
                event_type = "audio_synthesize"
            elif "/ask" in path:
                event_type = "ask_question"
            
            from app.models.analytics import UsageMetric
            metric = UsageMetric(
                event_type=event_type,
                endpoint=path[:100],
                response_time_ms=process_time,
                device_type=device
            )
            db.add(metric)
            db.commit()
            db.close()
        except:
            pass
    
    return response


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("quiz.html", {"request": request})


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
