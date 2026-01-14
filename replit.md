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
│   │   ├── learning.py        # Teaching sessions & mastery tracking
│   │   ├── practice_exam.py   # Timed mock certification exams
│   │   ├── spaced_repetition.py # SM-2 algorithm flashcard system
│   │   ├── peer_comparison.py # Anonymous leaderboards & rankings
│   │   ├── mentor.py          # Mentor matching & requests
│   │   ├── audio.py           # Text-to-speech study mode
│   │   ├── offline.py         # Downloadable study guide exports
│   │   └── pdf_viewer.py      # PDF viewing & download
│   ├── core/                   # Core configuration
│   │   ├── config.py          # App settings
│   │   └── database.py        # PostgreSQL connection
│   ├── models/                 # SQLAlchemy models
│   │   ├── user.py            # User model with relationships
│   │   ├── quiz.py            # Standard, StandardSection, QuizResult, SectionMastery, UserProgress
│   │   └── enhanced.py        # PracticeExam, SpacedRepetitionCard, PeerStats, Mentor, etc.
│   └── services/               # Business logic
│       ├── auth/              # JWT authentication
│       ├── rag/               # Vector store, PDF processing, AI services, PDF indexer
│       └── scraping/          # LVVTA website scraper
├── main.py                     # FastAPI app entry point
├── static/                     # Static files (CSS, JS)
├── templates/                  # HTML templates
├── pdf_cache/                  # Cached PDF downloads (30 PDFs)
├── audio_cache/                # Generated TTS audio files
├── study_exports/              # Downloadable study guides
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

**Phase E - Enhanced Learning Features - COMPLETE**
- Practice Exam Mode: Timed, multi-standard mock certification exams
- Spaced Repetition: SM-2 algorithm flashcards for struggling topics
- Progress Persistence: Quiz history saved to database across sessions
- PDF Viewer: Direct access to original LVVTA PDF documents
- Peer Comparison: Anonymous leaderboards and percentile rankings
- Audio Study Mode: Text-to-speech for hands-free learning
- Offline Mode: Downloadable JSON study guides with practice questions
- Mentor Matching: Connect trainees with experienced certifiers

## Tech Stack
- **Backend**: FastAPI, Python 3.11
- **Database**: PostgreSQL (Replit-managed)
- **Vector DB**: ChromaDB (persistent)
- **AI**: OpenAI via Replit AI Integrations (gpt-audio-mini for TTS)
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

### Practice Exam (NEW)
- `POST /api/practice-exam/start` - Start timed mock exam
- `GET /api/practice-exam/{exam_id}` - Get exam status & time remaining
- `POST /api/practice-exam/submit` - Submit exam answers
- `GET /api/practice-exam/history/all` - View exam history

### Spaced Repetition (NEW)
- `GET /api/spaced-repetition/due` - Get cards due for review
- `POST /api/spaced-repetition/review` - Submit card review (quality 0-5)
- `POST /api/spaced-repetition/generate` - Auto-generate cards from standard
- `POST /api/spaced-repetition/create` - Manually create flashcard
- `GET /api/spaced-repetition/stats` - View study statistics
- `DELETE /api/spaced-repetition/{card_id}` - Delete card

### Peer Comparison (NEW)
- `GET /api/peers/leaderboard` - Anonymous leaderboard
- `GET /api/peers/my-ranking` - Your rank & percentile
- `POST /api/peers/update-stats` - Refresh your statistics
- `GET /api/peers/category-rankings/{category}` - Category-specific rankings

### Mentors (NEW)
- `GET /api/mentors/` - List available mentors
- `GET /api/mentors/{mentor_id}` - Get mentor details
- `POST /api/mentors/request` - Request mentorship
- `GET /api/mentors/my-requests/` - View your requests
- `POST /api/mentors/register` - Register as mentor
- `PUT /api/mentors/status/{status}` - Update mentor availability

### Audio Study Mode (NEW)
- `POST /api/audio/synthesize` - Convert text to speech
- `POST /api/audio/standard` - Generate audio for standard content
- `GET /api/audio/file/{audio_hash}` - Download audio file
- `GET /api/audio/available/{standard_number}` - List audio sections

### Offline Mode (NEW)
- `POST /api/offline/export` - Create downloadable study guide
- `GET /api/offline/download/{export_id}` - Download study guide
- `GET /api/offline/my-exports` - List your exports
- `DELETE /api/offline/{export_id}` - Delete export
- `GET /api/offline/quick-reference/{category}` - Get category summary

### PDF Viewer (NEW)
- `GET /api/pdf/view/{standard_number}` - View PDF inline
- `GET /api/pdf/download/{standard_number}` - Download PDF
- `GET /api/pdf/available` - List cached PDFs
- `GET /api/pdf/info/{standard_number}` - Get PDF metadata

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
- 2026-01-14: Added 8 enhanced backend features (practice exams, spaced repetition, peer comparison, mentors, audio, offline, PDF viewer)
- 2026-01-14: Added comprehensive learning paths, scenario training, readiness tracker, and document viewer
- 2026-01-14: Indexed ORS Chapters 2-5, VIRM Threshold Guide, and 30+ LVV Standards from official PDFs
- 2026-01-14: Added interactive quiz frontend with login/register, AI question generation, answer evaluation, progress tracking
- 2026-01-14: Initial project setup with full infrastructure
