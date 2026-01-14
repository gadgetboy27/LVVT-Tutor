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
│       ├── rag/               # Vector store, PDF processing, AI services
│       └── scraping/          # LVVTA website scraper
├── main.py                     # FastAPI app entry point
├── static/                     # Static files (for frontend)
└── templates/                  # HTML templates
```

### Key Features (Roadmap Phases)

**Phase A - The "Brain" (AI) - COMPLETE**
- ChromaDB vector store for RAG
- PDF chunking with overlap for context
- OpenAI integration with citation requirements
- AI-powered summarization and categorization
- Core competency lookup (integrity, technical skill, etc.)

**Phase B - The "Heart" (Infrastructure) - COMPLETE**
- PostgreSQL database for users, scores, progress
- JWT authentication with bcrypt password hashing
- SQLAlchemy ORM with proper relationships
- Section-level mastery tracking (80% threshold)

**Phase C - The "Eyes" (Data Scraping) - COMPLETE**
- BeautifulSoup scraper for LVVTA website (https://lvvta.org.nz/documents.html)
- Change detection via Last-Modified headers
- Background task processing for updates
- Automatic categorization by topic (Brakes, Suspension, etc.)

**Phase D - Professional Polish (TODO)**
- Service Worker for offline mode (PWA)
- Side-by-side PDF viewer

## Tech Stack
- **Backend**: FastAPI, Python 3.11
- **Database**: PostgreSQL (Replit-managed)
- **Vector DB**: ChromaDB (persistent)
- **AI**: OpenAI via Replit AI Integrations
- **Auth**: JWT with python-jose, passlib/bcrypt
- **Scraping**: BeautifulSoup4, requests

## API Endpoints

### Authentication
- `POST /api/auth/register` - Create account
- `POST /api/auth/login` - Get JWT token
- `GET /api/auth/me` - Get current user

### Standards
- `GET /api/standards/` - List indexed standards
- `GET /api/standards/categories` - List all categories
- `GET /api/standards/by-category/{category}` - Filter by category
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
- `POST /api/quiz/submit` - Submit answers, save result
- `GET /api/quiz/history` - User's quiz history

## Core Competencies
The app emphasizes the soft skills required for LVV Certifiers:
- High level of integrity
- Technically skilled
- Vastly experienced
- Conscientious
- Independent
- Reliable
- Good people skills

## Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `AI_INTEGRATIONS_OPENAI_API_KEY` - OpenAI API key (managed by Replit)
- `AI_INTEGRATIONS_OPENAI_BASE_URL` - OpenAI base URL (managed by Replit)
- `SECRET_KEY` - JWT signing key

## Running the App
```bash
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

## Recent Changes
- 2026-01-14: Added interactive quiz frontend with login/register, AI question generation, answer evaluation, progress tracking, and resume capability
- 2026-01-14: Integrated LVV-Learn blueprint with teaching sessions, section mastery tracking, competency lookup, and AI summarization
- 2026-01-14: Initial project setup with full infrastructure
