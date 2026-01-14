# LVV-Learn: LVV Certifier Training App

## Overview
A production-ready FastAPI application for LVV (Low Volume Vehicle) certification training in New Zealand. The app transforms dense LVVTA technical documentation into an accessible, searchable, summarized, and interactive learning platform for aspiring LVV Certifiers.

## Architecture

### Project Structure
```
├── app/
│   ├── api/                    # API route handlers
│   │   ├── auth.py            # Authentication endpoints
│   │   ├── standards.py       # Standards & RAG Q&A endpoints
│   │   ├── quiz.py            # Quiz generation & submission
│   │   └── learning.py        # Teaching sessions & mastery tracking
│   ├── core/                   # Core configuration
│   │   ├── config.py          # App settings
│   │   └── database.py        # PostgreSQL connection
│   ├── models/                 # SQLAlchemy models
│   │   ├── user.py            # User model with relationships
│   │   └── quiz.py            # Standard, StandardSection, QuizResult, SectionMastery, UserProgress
│   └── services/               # Business logic
│       ├── auth/              # JWT authentication
│       ├── rag/               # Vector store, PDF processing, AI services, PDF indexer
│       └── scraping/          # LVVTA website scraper
├── main.py                     # FastAPI app entry point
├── static/                     # Static files (CSS, JS)
├── templates/                  # HTML templates
├── pdf_cache/                  # Cached PDF downloads
└── chroma_db/                  # ChromaDB vector store
```

### Key Features

**Phase A - The "Brain" (AI) - COMPLETE**
- ChromaDB vector store with 500+ indexed chunks from real LVVTA PDFs
- PDF downloading and text extraction from official LVVTA documents
- OpenAI integration with citation requirements
- AI-powered summarization, quiz generation, and answer evaluation

**Phase B - The "Heart" (Infrastructure) - COMPLETE**
- PostgreSQL database for users, scores, progress
- JWT authentication with bcrypt password hashing
- SQLAlchemy ORM with proper relationships
- Section-level mastery tracking (80% threshold)

**Phase C - The "Eyes" (Data Scraping) - COMPLETE**
- BeautifulSoup scraper for LVVTA website (https://lvvta.org.nz/documents.html)
- 30+ real LVVTA standards indexed from official PDFs
- ORS Chapters 2, 3, 4, 5 fully indexed (418 chunks)
- VIRM Threshold Guide indexed (39 chunks)

**Phase D - Learning Paths & Readiness - COMPLETE**
- Certification category learning paths (1A-1D, 2A-2C, 3A-3B, RH, ORS, VIRM)
- Scenario-based certification decision training
- Core competency self-assessment (7 pillars)
- Certification readiness tracker with visual progress
- "Read Document" option before taking quiz
- Document viewer with back button

## Tech Stack
- **Backend**: FastAPI, Python 3.11
- **Database**: PostgreSQL (Replit-managed)
- **Vector DB**: ChromaDB (persistent)
- **AI**: OpenAI via Replit AI Integrations
- **Auth**: JWT with python-jose, passlib/bcrypt
- **Scraping**: BeautifulSoup4, requests, PyPDF2

## API Endpoints

### Authentication
- `POST /api/auth/register` - Create account
- `POST /api/auth/login` - Get JWT token
- `GET /api/auth/me` - Get current user

### Standards
- `GET /api/standards/` - List indexed standards
- `GET /api/standards/categories` - List all categories
- `GET /api/standards/by-category/{category}` - Filter by category
- `GET /api/standards/content/{standard_number}` - Get document content from vector store
- `GET /api/standards/{standard_number}` - Get details with sections
- `POST /api/standards/update` - Scrape & index new standards
- `POST /api/standards/search` - Search across all standards
- `POST /api/standards/ask` - RAG Q&A with citations

### Learning & Mastery
- `GET /api/learning/competencies` - List core competencies
- `POST /api/learning/competency` - Get competency explanation
- `GET /api/learning/teaching/{standard_number}` - Start teaching session
- `POST /api/learning/section-quiz` - Generate section quiz
- `POST /api/learning/section-quiz/submit` - Submit & record mastery
- `GET /api/learning/progress/summary` - Get overall progress

### Quiz
- `POST /api/quiz/generate` - Generate quiz for a standard
- `POST /api/quiz/evaluate-answer` - AI evaluation of answers
- `POST /api/quiz/submit` - Submit answers, save result
- `GET /api/quiz/history` - User's quiz history

## Core Competencies (7 Pillars)
The app emphasizes the soft skills required for LVV Certifiers:
1. High level of integrity
2. Technically skilled
3. Vastly experienced (10+ years)
4. Conscientious
5. Independent
6. Reliable
7. Good people skills

## Certification Categories
- **1A, 1B, 1C, 1D** - General motor vehicles
- **2A, 2B, 2C** - Motorcycles and trikes
- **3A, 3B** - Disability transportation
- **4** - Commercial modifications
- **RH** - Right-hand drive conversions

## Indexed Content
- ORS Chapter 2: Low Volume Vehicle Classifications (40 chunks)
- ORS Chapter 3: LVV Certification Categories (45 chunks)
- ORS Chapter 4: LVV Certifier Background Criteria (34 chunks)
- ORS Chapter 5: LVV Certifier Application & Appointment (79 chunks)
- Complete ORS (220 chunks)
- VIRM Threshold Guide (39 chunks)
- 21 LVV Technical Standards (Braking, Suspension, Engine, etc.)

## Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `AI_INTEGRATIONS_OPENAI_API_KEY` - OpenAI API key (managed by Replit)
- `AI_INTEGRATIONS_OPENAI_BASE_URL` - OpenAI base URL (managed by Replit)
- `SECRET_KEY` - JWT signing key

## Running the App
```bash
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

## User Flow
1. Login (mock auth for testing)
2. Navigate using top nav: Dashboard | Learning Paths | Scenarios | Readiness Check
3. Select a topic category on Dashboard
4. Choose to "Read Document" first or go directly to "Take Quiz"
5. Document viewer shows indexed content with "Back" and "Take Quiz" buttons
6. Complete quizzes to build mastery and track readiness
7. Complete self-assessment of 7 core competencies
8. Monitor overall certification readiness percentage

## Recent Changes
- 2026-01-14: Added comprehensive learning paths, scenario training, readiness tracker, and document viewer
- 2026-01-14: Indexed ORS Chapters 2-5, VIRM Threshold Guide, and 30+ LVV Standards from official PDFs
- 2026-01-14: Added interactive quiz frontend with login/register, AI question generation, answer evaluation, progress tracking
- 2026-01-14: Initial project setup with full infrastructure
