# LVV Standards Training App

## Overview
A production-ready FastAPI application for LVV (Low Volume Vehicle) certification training in New Zealand. The app provides RAG-powered Q&A, AI-generated quizzes, and progress tracking for certifiers.

## Architecture

### Project Structure
```
├── app/
│   ├── api/                    # API route handlers
│   │   ├── auth.py            # Authentication endpoints
│   │   ├── standards.py       # Standards & RAG Q&A endpoints
│   │   └── quiz.py            # Quiz generation & submission
│   ├── core/                   # Core configuration
│   │   ├── config.py          # App settings
│   │   └── database.py        # PostgreSQL connection
│   ├── models/                 # SQLAlchemy models
│   │   ├── user.py            # User model
│   │   └── quiz.py            # Standard, QuizResult, UserProgress
│   └── services/               # Business logic
│       ├── auth/              # JWT authentication
│       ├── rag/               # Vector store, PDF processing, AI
│       └── scraping/          # LVVTA website scraper
├── main.py                     # FastAPI app entry point
├── static/                     # Static files (for frontend)
└── templates/                  # HTML templates
```

### Key Features (Roadmap Phases)

**Phase A - The "Brain" (AI)**
- ChromaDB vector store for RAG
- PDF chunking with overlap for context
- OpenAI integration with citation requirements
- Query relevant sections instead of full documents

**Phase B - The "Heart" (Infrastructure)**
- PostgreSQL database for users, scores, progress
- JWT authentication with bcrypt password hashing
- SQLAlchemy ORM with proper relationships

**Phase C - The "Eyes" (Data Scraping)**
- BeautifulSoup scraper for LVVTA website
- Change detection via Last-Modified headers
- Background task processing for updates

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
- `POST /api/standards/update` - Scrape & index new standards
- `POST /api/standards/ask` - RAG Q&A with citations

### Quiz
- `POST /api/quiz/generate` - Generate quiz for a standard
- `POST /api/quiz/submit` - Submit answers, save result
- `GET /api/quiz/history` - User's quiz history

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
- 2026-01-14: Initial project setup with full infrastructure
