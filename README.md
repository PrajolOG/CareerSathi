# Career Sathi (करियर साथी)

Career Sathi is an AI-powered career counseling platform designed specifically for Nepali students. It provides personalized guidance, academic analysis, and career roadmaps to help students navigate their journey from high school to professional success.

## Key Features

- **AI Career Counselor**: Interactive chat powered by Google Gemini for real-time career advice.
- **Academic Analysis**: Upload academic documents (PDF/DOCX) for AI-driven insights and recommendations.
- **Nepal-Centric Guidance**: Tailored advice accounting for the Nepali education system (+2, Bachelors) and local job market.
- **Personalized Roadmaps**: Goal-oriented planning to help students reach the "summit" of their careers.
- **Secure Authentication**: Robust user management integrated with Supabase.

## Technology Stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **AI Engine**: [Google Gemini AI](https://ai.google.dev/) (via Google Generative AI SDK)
- **Database & Auth**: [Supabase](https://supabase.com/)
- **Frontend**: Clean, responsive UI built with Vanilla HTML5, CSS3, and JavaScript.
- **Package Manager**: [uv](https://github.com/astral-sh/uv)

## Getting Started

1.  **Environment Setup**:
    -   Create a `.env` file with your `SUPABASE_URL`, `SUPABASE_KEY`, and `GOOGLE_API_KEY`.
2.  **Run the Application**:
    ```bash
    uv run uvicorn app.main:app --reload
    ```
