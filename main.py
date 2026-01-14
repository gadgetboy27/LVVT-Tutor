from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.core.database import engine, Base
from app.api.auth import router as auth_router
from app.api.standards import router as standards_router
from app.api.quiz import router as quiz_router
from app.api.learning import router as learning_router

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

app.include_router(auth_router)
app.include_router(standards_router)
app.include_router(quiz_router)
app.include_router(learning_router)


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>LVV-Learn: LVV Certifier Training</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 900px; margin: 50px auto; padding: 20px; background: #f9f9f9; }
            h1 { color: #1a5f7a; }
            h2 { color: #333; margin-top: 30px; }
            .feature { background: #fff; padding: 15px 20px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #1a5f7a; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .endpoint { background: #fff; padding: 12px 15px; margin: 8px 0; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
            .method { font-weight: bold; padding: 3px 8px; border-radius: 4px; margin-right: 8px; }
            .get { background: #61affe; color: white; }
            .post { background: #49cc90; color: white; }
            code { background: #e9e9e9; padding: 2px 6px; border-radius: 3px; font-family: monospace; }
            .section { margin-bottom: 25px; }
            a { color: #1a5f7a; }
        </style>
    </head>
    <body>
        <h1>LVV-Learn: LVV Certifier Training API</h1>
        <p>Transform dense LVVTA technical documentation into an accessible, searchable, and interactive learning platform for aspiring Low Volume Vehicle (LVV) Certifiers.</p>
        
        <h2>Key Features</h2>
        <div class="feature">
            <strong>RAG-powered Q&A</strong> - Ask questions about LVV standards and get answers with specific citations (e.g., "According to LVV Standard 40-10, Section 2.1...")
        </div>
        <div class="feature">
            <strong>AI Quiz Generation</strong> - Generate quizzes from any standard or section to test your understanding
        </div>
        <div class="feature">
            <strong>Section Mastery Tracking</strong> - Track which sections you've mastered (80% or higher) to focus on areas that need work
        </div>
        <div class="feature">
            <strong>Core Competencies</strong> - Learn about the soft skills required: integrity, technical skill, experience, reliability
        </div>
        <div class="feature">
            <strong>Auto-sync Standards</strong> - Scrapes and indexes PDFs from the LVVTA website with change detection
        </div>
        
        <div class="section">
            <h2>Authentication</h2>
            <div class="endpoint">
                <span class="method post">POST</span> <code>/api/auth/register</code> - Create a new account
            </div>
            <div class="endpoint">
                <span class="method post">POST</span> <code>/api/auth/login</code> - Login and get JWT token
            </div>
            <div class="endpoint">
                <span class="method get">GET</span> <code>/api/auth/me</code> - Get current user info
            </div>
        </div>
        
        <div class="section">
            <h2>Standards & RAG Q&A</h2>
            <div class="endpoint">
                <span class="method get">GET</span> <code>/api/standards/</code> - List all indexed standards
            </div>
            <div class="endpoint">
                <span class="method get">GET</span> <code>/api/standards/categories</code> - List all categories
            </div>
            <div class="endpoint">
                <span class="method get">GET</span> <code>/api/standards/{standard_number}</code> - Get standard details with sections
            </div>
            <div class="endpoint">
                <span class="method post">POST</span> <code>/api/standards/update</code> - Scrape & index new standards
            </div>
            <div class="endpoint">
                <span class="method post">POST</span> <code>/api/standards/search</code> - Search across all standards
            </div>
            <div class="endpoint">
                <span class="method post">POST</span> <code>/api/standards/ask</code> - Ask a question (RAG with citations)
            </div>
        </div>
        
        <div class="section">
            <h2>Learning & Mastery</h2>
            <div class="endpoint">
                <span class="method get">GET</span> <code>/api/learning/competencies</code> - List core competencies
            </div>
            <div class="endpoint">
                <span class="method post">POST</span> <code>/api/learning/competency</code> - Get competency explanation
            </div>
            <div class="endpoint">
                <span class="method get">GET</span> <code>/api/learning/teaching/{standard_number}</code> - Start teaching session
            </div>
            <div class="endpoint">
                <span class="method post">POST</span> <code>/api/learning/section-quiz</code> - Generate section quiz
            </div>
            <div class="endpoint">
                <span class="method post">POST</span> <code>/api/learning/section-quiz/submit</code> - Submit quiz & record mastery
            </div>
            <div class="endpoint">
                <span class="method get">GET</span> <code>/api/learning/progress/summary</code> - Get overall progress
            </div>
        </div>
        
        <div class="section">
            <h2>Quiz</h2>
            <div class="endpoint">
                <span class="method post">POST</span> <code>/api/quiz/generate</code> - Generate quiz for a standard
            </div>
            <div class="endpoint">
                <span class="method post">POST</span> <code>/api/quiz/submit</code> - Submit answers, save result
            </div>
            <div class="endpoint">
                <span class="method get">GET</span> <code>/api/quiz/history</code> - Get your quiz history
            </div>
        </div>
        
        <p style="margin-top: 30px;"><a href="/docs">View Interactive API Docs (Swagger)</a> | <a href="/redoc">ReDoc</a></p>
    </body>
    </html>
    """


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
