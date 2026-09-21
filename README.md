# Reachwell: Inter Guild Buildathon

Multi-channel autonomous SDR system: a campaign control plane (React + FastAPI)
plus an agentic outreach engine built on DronaHQ.

## Structure
- `frontend/`  React + Vite + TypeScript control plane UI
- `backend/`   FastAPI service (campaigns, prompts, reps, controls)
- `agents/`    AI agents and RAG code
- `docs/`      Architecture diagram and report

## Setup
### Backend
    cd backend
    python -m venv venv
    venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    uvicorn app.main:app --reload

### Frontend
    cd frontend
    npm install
    npm run dev

## Environment variables
See `.env.example` and `backend/.env.example`.

## Tech stack
React, Vite, TypeScript, Tailwind, shadcn/ui, FastAPI, SQLAlchemy, DronaHQ.