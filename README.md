# Proteus: MCMC Protein Design Platform

A production-grade protein design platform combining Markov Chain Monte Carlo with machine learning to discover novel protein therapeutics targeting oncology targets. For research use only.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  React SPA  │────▶│  FastAPI     │────▶│  PostgreSQL │
│  (Vite +    │     │  (Uvicorn)   │     │  (Results,  │
│  Tailwind)  │◀────│              │◀────│  Audit)     │
└─────────────┘     │  + WebSocket │     └─────────────┘
       │            │  + Redis RQ  │     ┌─────────────┐
       │            └──────────────┘────▶│  Redis      │
       ▼                                 │  (Job Queue)│
┌─────────────┐                          └─────────────┘
│  PDBe       │
│  Molstar    │
│  3D Viewer  │
└─────────────┘
```

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic
- **Frontend:** React 18, Vite, TailwindCSS, Recharts, PDBe Molstar
- **Database:** PostgreSQL 14+
- **MCMC Core:** NumPy, SciPy (from first principles)
- **Async:** FastAPI background tasks + Redis for job queuing
- **Testing:** pytest, pytest-asyncio

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (recommended)

### Local Development (All Services)

```bash
# Start PostgreSQL and Redis
docker-compose up -d db redis

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend setup (new terminal)
cd frontend
npm install
npm run dev
```

### Using Docker Compose (Full Stack)

```bash
docker-compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
proteus/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI route handlers
│   │   ├── core/          # MCMC engine (energy, proposal, sampler)
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── services/      # Business logic (audit, compliance, jobs)
│   │   └── ws/            # WebSocket manager
│   ├── tests/             # pytest test suite
│   ├── alembic/           # Database migrations
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/    # Reusable UI components
│   │   ├── pages/         # Route pages
│   │   ├── services/      # API client & WebSocket
│   │   ├── hooks/         # React hooks & state
│   │   └── types/         # TypeScript definitions
│   └── Dockerfile
├── data/
│   ├── targets/           # Target protein PDB files
│   ├── known_binders/     # Known binder CSV datasets
│   ├── models/            # ML model weights & embeddings
│   └── mcmc_params.yaml   # MCMC configuration
├── docker-compose.yml     # Multi-service orchestration
└── README.md
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login
- `GET /api/v1/auth/me` - Get current user
- `PUT /api/v1/auth/me` - Update profile
- `POST /api/v1/auth/refresh` - Refresh token

### Targets
- `GET /api/v1/targets` - List all targets
- `GET /api/v1/targets/{name}` - Get target details
- `GET /api/v1/targets/{name}/binders` - Get known binders

### MCMC Runs
- `POST /api/v1/runs` - Create new design run
- `GET /api/v1/runs` - List user's runs
- `GET /api/v1/runs/{id}` - Get run details
- `GET /api/v1/runs/{id}/mutations` - Get mutation trace
- `GET /api/v1/runs/{id}/download` - Download run as JSON
- `POST /api/v1/runs/{id}/cancel` - Cancel running job
- `POST /api/v1/runs/compare` - Compare two runs

### Admin
- `GET /api/v1/admin/users` - List users (admin only)
- `PUT /api/v1/admin/users/{id}` - Update user (admin only)
- `GET /api/v1/admin/audit-logs` - View audit log (admin only)
- `POST /api/v1/admin/cleanup` - Data retention cleanup

### WebSocket
- `WS /api/v1/runs/{id}/ws` - Real-time run progress stream

## Configuration

MCMC parameters are configured in `data/mcmc_params.yaml`:

- **Temperatures:** `[0.5, 1.0, 2.0, 5.0, 10.0]` (temperature ladder)
- **Chains:** 5 parallel chains with periodic swapping
- **Steps:** 1000 steps per chain (configurable)
- **Proposal ops:** point (70%), ESM-guided (20%), block (8%), LLM jump (2%)

## Data Retention

Runs are automatically cleaned up after 365 days (configurable via `DATA_RETENTION_DAYS`). Archived runs are preserved. Admin can trigger manual cleanup via the admin panel.

## Compliance

- **For Research Use Only:** Not a medical device. Candidates must undergo wet-lab validation.
- **Audit Trail:** All API calls logged to `audit_logs` table with timestamps, user, action, parameters, and results hash.
- **Dual-Use Screening:** Optional sequence screening for dual-use research concerns.
- **Data Encryption:** Fernet encryption available for sensitive data (when enabled).
- **TLS Ready:** Configure TLS/HTTPS in production deployment.

## Testing

```bash
cd backend
pytest tests/ -v

# Run specific test categories
pytest tests/test_mcmc.py -v
pytest tests/test_energy.py -v
pytest tests/test_api.py -v
```

## Deployment

### Production Deployment

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Deploy (example with AWS ECS/GCP Cloud Run/Azure ACI)
docker-compose -f docker-compose.prod.yml up -d
```

### Cloud Deployment Notes

- **Database:** Use managed PostgreSQL (AWS RDS, GCP Cloud SQL, Azure Database)
- **Redis:** Use managed Redis (AWS ElastiCache, GCP Memorystore, Azure Cache)
- **Frontend:** Build static site (`npm run build`), deploy to S3+CloudFront/GCP Storage+CDN
- **MCMC Compute:** Long-running jobs can offload to Modal or AWS Lambda
- **Scaling:** Stateless backend can scale horizontally behind load balancer

## License

FOR RESEARCH USE ONLY. Not a medical device. All designs must undergo wet-lab validation.

For research use only.
