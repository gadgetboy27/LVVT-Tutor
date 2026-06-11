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
from app.api.teach import router as teach_router
from app.models.quiz import Standard

from app.models import enhanced, analytics

Base.metadata.create_all(bind=engine)


def seed_initial_standards():
    db = SessionLocal()
    try:
        # standard_number values must match the names indexed in ChromaDB so the
        # PDF viewer routes (and backfill_pdf_urls) can resolve each standard's
        # cached PDF. Keep these aligned with the indexed corpus.
        initial_standards = [
            {"standard_number": "LVVTA_STD_Braking_Systems", "title": "Braking Systems", "category": "Brakes", "summary": "LVVTA standard covering braking systems"},
            {"standard_number": "LVVTA_STD_Chassis_Modification_Construction", "title": "Chassis Modification & Construction", "category": "Body & Structure", "summary": "LVVTA standard covering chassis modification and construction"},
            {"standard_number": "LVVTA_STD_Engine_&_Drive-train_Conversions", "title": "Engine & Drive-train Conversions", "category": "Engine & Drivetrain", "summary": "LVVTA standard covering engine and drive-train conversions"},
            {"standard_number": "LVVTA_STD_Exhaust_Noise_Emissions", "title": "Exhaust Noise Emissions", "category": "Exhaust & Emissions", "summary": "LVVTA standard covering exhaust noise emissions"},
            {"standard_number": "LVVTA_STD_Exhaust_Gas_Emissions", "title": "Exhaust Gas Emissions", "category": "Exhaust & Emissions", "summary": "LVVTA standard covering exhaust gas emissions"},
            {"standard_number": "LVVTA_STD_Fuel_Systems", "title": "Fuel Systems", "category": "Fuel Systems", "summary": "LVVTA standard covering fuel systems"},
            {"standard_number": "LVVTA_STD_Lighting_Equipment", "title": "Lighting Equipment", "category": "Lighting & Electrical", "summary": "LVVTA standard covering lighting equipment"},
            {"standard_number": "LVVTA_STD_Suspension_Systems", "title": "Suspension Systems", "category": "Suspension & Steering", "summary": "LVVTA standard covering suspension systems"},
            {"standard_number": "LVVTA_STD_Wheels_&_Tyres", "title": "Wheels & Tyres", "category": "Wheels & Tyres", "summary": "LVVTA standard covering wheels and tyres"},
            {"standard_number": "ORS_Chapter_3", "title": "ORS Chapter 3 - Certification Categories", "category": "Certification Process", "summary": "LVV Certification categories and requirements"},
            {"standard_number": "ORS_Chapter_4", "title": "ORS Chapter 4 - Certifier Criteria", "category": "Certification Process", "summary": "LVV Certifier background criteria"},
            {"standard_number": "ORS_Chapter_5", "title": "ORS Chapter 5 - Application Process", "category": "Certification Process", "summary": "LVV Certifier application and appointment"},
        ]
        
        added_count = 0
        for std_data in initial_standards:
            exists = db.query(Standard).filter(
                Standard.standard_number == std_data["standard_number"]
            ).first()
            if not exists:
                std = Standard(**std_data)
                db.add(std)
                added_count += 1
        
        if added_count > 0:
            db.commit()
            print(f"Seeded {added_count} missing standards")
        else:
            count = db.query(Standard).count()
            print(f"All standards present ({count} total)")
    except Exception as e:
        print(f"Error seeding standards: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_initial_standards()
    try:
        from app.services.rag.pdf_indexer import seed_standards_from_chroma, backfill_pdf_urls
        # Pull the full indexed corpus into the DB (title/category/pdf_url) so
        # every category and learning path is populated.
        seeded = seed_standards_from_chroma()
        if seeded.get("created") or seeded.get("updated"):
            print(f"Seeded {seeded.get('created', 0)} and updated {seeded.get('updated', 0)} standards from ChromaDB")
        # Safety net for any remaining rows missing a pdf_url.
        result = backfill_pdf_urls()
        if result.get("updated"):
            print(f"Backfilled pdf_url for {result['updated']} standards from ChromaDB")
    except Exception as e:
        print(f"Standard seeding from ChromaDB skipped: {e}")
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
app.include_router(teach_router)


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
    return templates.TemplateResponse(request, "quiz.html")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
