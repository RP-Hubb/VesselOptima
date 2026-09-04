# VesselOptima — Freight Intelligence & Procurement Optimization Platform

## SIH26006 — Development of an Intelligent Freight Forecasting Model

VesselOptima is an integrated freight intelligence, chartering feasibility,
and procurement optimization platform for bulk-cargo logistics.

**Core principle:** PREDICT → CONSTRAIN → OPTIMIZE → STRESS TEST → DECIDE → AUDIT

## Project Structure

```
VesselOptima/
├── backend/          # FastAPI + SQLAlchemy + Alembic
│   ├── app/          # Application package
│   │   ├── api/      # API route handlers
│   │   ├── core/     # Configuration, logging, exceptions
│   │   ├── db/       # Database session and base
│   │   ├── models/   # SQLAlchemy ORM models
│   │   ├── schemas/  # Pydantic request/response schemas
│   │   ├── services/ # Business logic services
│   │   ├── engines/  # Domain engines (Phase 2+)
│   │   └── main.py   # FastAPI application entry point
│   ├── tests/        # Backend tests
│   ├── alembic/      # Database migrations
│   └── .env.example  # Environment configuration template
├── frontend/         # Next.js + TypeScript + Tailwind CSS
├── data/             # Data storage (offline packages, raw, processed)
├── models/           # ML model artifacts
├── docs/             # Documentation and contracts
├── scripts/          # Build and validation scripts
├── docker/           # Docker configuration
└── tests/            # Integration and E2E tests
```

## Runtime Modes

VesselOptima supports exactly **two** runtime modes:

- **LIVE** — External data sources, live ingestion
- **OFFLINE_DEMO** — Frozen local dataset, no network access

There is no hybrid mode. There is no automatic fallback.

## Quick Start

### Backend
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate     # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## API Documentation

Once the backend is running: http://localhost:8000/docs
