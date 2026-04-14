# Career Sathi (करियर साथी)

Career Sathi is Nepal's first AI-powered career counseling platform designed specifically for Nepali students. The platform combines machine learning predictions with an intelligent AI counselor to guide students through academic and career decisions, from +2 level through undergraduate studies.

## Overview

Career Sathi addresses the critical gap in career guidance for Nepali students by providing culturally relevant, data-driven recommendations. The platform understands the Nepali education system including +2 streams, TU/KU/PU affiliations, and entrance examinations like IOE, CMAT, and CEE.

## Key Features

### AI Career Counselor
- Interactive chat interface powered by Google Gemini
- Context-aware conversations that remember student profiles
- Real-time guidance on entrance exams, college selection, and career paths
- Document upload support for personalized analysis (PDF and image files)

### Career Prediction Engine
- Machine learning model trained on academic and career data
- Top 3 career matches based on grades, interests, and aptitude
- Confidence scoring with detailed reasoning
- Personalized roadmaps for each recommended path

### College Finder
- Curated database of Nepali universities and colleges
- Filter by entrance exam requirements (IOE, CMAT, CEE, etc.)
- Global institution recommendations for study abroad options
- Course-specific suggestions aligned with career predictions

### Academic Analysis
- Document upload and OCR processing for PDF and image files
- Grade extraction and academic performance analysis
- Interest assessment through interactive questionnaires
- Strength identification across subjects and skills

### User Management
- Secure authentication via Supabase
- Persistent chat history and conversation threads
- Career report generation with PDF export capability
- Avatar selection and profile customization
- Account settings with education level and gender preferences

### Security and Limits
- Rate limiting on login attempts and chat messages
- Context reset functionality for privacy
- Chat history deletion with permanent removal
- Usage tracking with fair-use policies

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.12+)
- **Authentication**: Supabase Auth
- **Database**: Supabase PostgreSQL
- **AI Engine**: Google Gemini 2.5 Flash
- **ML Framework**: scikit-learn, joblib
- **Document Processing**: PyMuPDF, pytesseract

### Frontend
- **Templating**: Jinja2 with FastAPI
- **Styling**: Vanilla CSS3 with CSS custom properties
- **Icons**: Font Awesome 6
- **Fonts**: Plus Jakarta Sans, Noto Sans Devanagari

### Infrastructure
- **Package Manager**: uv
- **Object Storage**: MinIO (avatar storage)
- **Search**: Tavily API (college and career search)

## Project Structure

```
Career Sathi/
├── app/
│   ├── main.py                 # FastAPI application entrypoint
│   ├── database.py             # Supabase client and DB operations
│   ├── rate_limiter.py         # Rate limiting middleware
│   ├── schemas.py              # Pydantic data models
│   ├── minio_handler.py        # Avatar storage operations
│   ├── chat_upload_meta.py     # Chat metadata handling
│   ├── routers/                # API route handlers
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── chat.py             # Chat and messaging endpoints
│   │   ├── profile.py          # User profile endpoints
│   │   ├── reports.py          # Career report endpoints
│   │   ├── admin.py            # Admin operations
│   │   └── search.py           # Search endpoints
│   └── services/               # Business logic layer
│       ├── chat_service.py     # Chat orchestration
│       ├── ml_service.py       # ML prediction model
│       ├── gemini_pool.py      # Gemini API management
│       ├── ocr_service.py      # Document OCR processing
│       ├── email_service.py    # Email notifications
│       ├── tavily_service.py   # External search integration
│       └── password_reset_service.py  # Password recovery
├── templates/                  # Jinja2 HTML templates
│   ├── index.html              # Landing page
│   ├── login.html              # Authentication pages
│   ├── signup.html
│   ├── userprofile.html        # User dashboard
│   ├── chat.html               # AI chat interface
│   ├── settings.html           # Account settings
│   └── shared_navbar.html      # Shared navigation component
├── static/                     # Static assets
│   ├── css/                    # Stylesheets
│   ├── assets/                 # Images and icons
│   └── uploads/                # User uploads (temporary)
├── model/                      # Trained ML models
│   └── career_recommender_v1.pkl
├── data/                       # Training data and encoders
└── pyproject.toml              # Project dependencies
```

## Getting Started

### Prerequisites
- Python 3.12 or higher
- uv package manager
- MinIO instance (for avatar storage)
- Supabase project
- Google Cloud API key with Gemini access

### Environment Setup

Create a `.env` file in the project root:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
GOOGLE_API_KEY=your-gemini-api-key
MINIO_ENDPOINT=your-minio-endpoint
MINIO_ACCESS_KEY=your-access-key
MINIO_SECRET_KEY=your-secret-key
MINIO_BUCKET_NAME=career-sathi-avatars
TAVILY_API_KEY=your-tavily-key
```

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd "Career Sathi"

# Install dependencies with uv
uv sync

# Run the development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at `http://localhost:8000`.

## API Endpoints

### Authentication
- `POST /auth/signup` - User registration
- `POST /auth/login` - User login
- `POST /auth/logout` - Session termination
- `POST /auth/reset-password` - Password reset

### Chat
- `GET /chat` - Chat interface (HTML)
- `POST /chat/message` - Send message to AI
- `GET /chat/history` - Retrieve chat history
- `DELETE /chat/history` - Clear chat history

### Profile
- `GET /userProfile` - User dashboard
- `POST /settings/update` - Update profile settings
- `GET /profile/context` - Get AI context
- `DELETE /profile/context` - Reset AI context

### Reports
- `GET /reports` - Career reports dashboard
- `POST /reports/generate` - Generate new report
- `GET /reports/{id}` - View specific report

## Configuration

### Rate Limits
- Login attempts: 5 per minute
- Chat messages: 10 per minute
- Career reports: Maximum 3 per user

### Supported File Types
- Document uploads: PDF, PNG, JPG, JPEG
- Maximum file size: 10MB

## Development

### Running Tests
```bash
uv run pytest
```

### Code Quality
```bash
uv run ruff check .
uv run ruff format .
```

## License

Copyright 2026 Career Sathi. All rights reserved.

## Contact

For support or inquiries, contact the development team.
