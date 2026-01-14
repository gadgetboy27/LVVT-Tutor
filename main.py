from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from app.core.database import engine, Base
from app.api.auth import router as auth_router
from app.api.standards import router as standards_router
from app.api.quiz import router as quiz_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LVV Standards Training API",
    description="API for LVV certification training with RAG-powered Q&A and quizzes",
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


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>LVV Standards Training API</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #333; }
            .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 8px; }
            .method { font-weight: bold; color: #007bff; }
            code { background: #e9e9e9; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <h1>LVV Standards Training API</h1>
        <p>Production-ready API for LVV certification training.</p>
        
        <h2>Features</h2>
        <ul>
            <li><strong>RAG-powered Q&A</strong> - Ask questions about LVV standards with cited answers</li>
            <li><strong>Quiz Generation</strong> - AI-generated quizzes from standard content</li>
            <li><strong>JWT Authentication</strong> - Secure user accounts and progress tracking</li>
            <li><strong>Web Scraping</strong> - Auto-sync standards from LVVTA website</li>
        </ul>
        
        <h2>API Endpoints</h2>
        
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/auth/register</code> - Register new user
        </div>
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/auth/login</code> - Login and get JWT token
        </div>
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/standards/</code> - List all indexed standards
        </div>
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/standards/update</code> - Scrape and index new standards
        </div>
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/standards/ask</code> - Ask a question (RAG)
        </div>
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/quiz/generate</code> - Generate quiz for a standard
        </div>
        <div class="endpoint">
            <span class="method">POST</span> <code>/api/quiz/submit</code> - Submit quiz answers
        </div>
        <div class="endpoint">
            <span class="method">GET</span> <code>/api/quiz/history</code> - Get user's quiz history
        </div>
        
        <p><a href="/docs">View Interactive API Docs (Swagger)</a></p>
    </body>
    </html>
    """


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
