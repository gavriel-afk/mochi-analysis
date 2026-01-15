# Mochi Analytics v2.0

Modern analytics platform for Mochi conversation data with FastAPI backend, PostgreSQL storage, and comprehensive analysis features.

## Features

- **6 Analysis Features**: Core metrics, setter analysis, time series, script clustering, objection classification, avatar clustering
- **4 Export Formats**: JSON, CSV (Framer CMS), PNG charts, Slack Block Kit
- **External Integrations**: Mochi API, Airtable, Slack, Framer CMS, Google Gemini
- **REST API**: FastAPI with 20+ endpoints
- **Database Storage**: PostgreSQL/SQLite with SQLAlchemy

---

## Quick Start

### 1. Install

```bash
cd mochi-analytics
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements/base.txt
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required environment variables:
- `MOCHI_SESSION_ID` - Django session cookie
- `GOOGLE_API_KEY` - For LLM features
- `AIRTABLE_API_KEY` - Organization configs
- `AIRTABLE_BASE_ID` - Airtable base
- `SLACK_BOT_TOKEN` - Slack notifications
- `FRAMER_API_URL` - Framer CMS endpoint

### 3. Start Server

```bash
uvicorn mochi_analytics.api:app --reload --port 8000
```

Visit: **http://localhost:8000/docs**

---

## API Usage

### Health Check

```bash
curl http://localhost:8000/health
```

### List Organizations

```bash
curl http://localhost:8000/api/v1/organizations
```

### Submit Analysis

```bash
curl -X POST http://localhost:8000/api/v1/analysis \
  -H "Content-Type: application/json" \
  -d '{
    "conversations": [...],
    "config": {
      "timezone": "UTC",
      "start_date": "2025-01-01",
      "end_date": "2025-01-07"
    }
  }'
```

### Get Results

```bash
curl http://localhost:8000/api/v1/analysis/{job_id}
```

### Export Formats

```bash
# JSON
curl http://localhost:8000/api/v1/exports/{job_id}/json -o report.json

# CSV (Framer CMS)
curl http://localhost:8000/api/v1/exports/{job_id}/csv -o import.csv

# Complete bundle (JSON + CSV + charts)
curl http://localhost:8000/api/v1/exports/{job_id}/zip -o bundle.zip

# Individual chart
curl http://localhost:8000/api/v1/exports/{job_id}/charts/01_new_leads.png -o chart.png
```

---

## API Endpoints

**Analysis**
- `POST /api/v1/analysis` - Submit job
- `GET /api/v1/analysis/{job_id}` - Get status

**Jobs**
- `GET /api/v1/jobs` - List all jobs
- `GET /api/v1/jobs/{job_id}` - Get job details
- `POST /api/v1/jobs/{job_id}/retry` - Retry failed job

**Exports**
- `GET /api/v1/exports/{job_id}/json` - JSON export
- `GET /api/v1/exports/{job_id}/csv` - CSV export
- `GET /api/v1/exports/{job_id}/zip` - ZIP bundle
- `GET /api/v1/exports/{job_id}/charts/{chart_id}.png` - Chart image

**Organizations**
- `GET /api/v1/organizations` - List orgs
- `GET /api/v1/organizations/{org_id}` - Get org
- `POST /api/v1/organizations/{org_id}/analyze` - Analyze org

**Reports**
- `POST /api/v1/reports` - Create report
- `GET /api/v1/reports` - List reports
- `GET /api/v1/reports/{slug}` - Get report

**Tasks**
- `POST /api/v1/tasks/daily-updates` - Run daily Slack digests
- `POST /api/v1/tasks/auto-export` - Run auto-export

---

## Project Structure

```
mochi-analytics/
├── src/mochi_analytics/
│   ├── core/              # Analysis engine
│   ├── storage/           # Database models
│   ├── api/               # FastAPI server
│   ├── exporters/         # Export formats
│   └── integrations/      # External APIs
├── config/                # Configuration files
├── requirements/          # Dependencies
└── alembic/              # Database migrations
```

---

## Analysis Features

1. **Core Metrics** - Conversations, messages, reply rates, stage changes
2. **Setter Analysis** - Per-setter performance (by sender, by assignment)
3. **Time Series** - Daily stage changes, activity by time of day
4. **Script Analysis** - Fuzzy matching + Gemini categorization
5. **Objection Classification** - Gemini batch classification (7 categories)
6. **Avatar Clustering** - Gemini embeddings + K-means (5 personas)

---

## Database

The system uses database-first storage (no ephemeral filesystem):
- Analysis results → JSONB field
- Chart PNGs → Base64 TEXT field
- Reports → JSONB field
- Avatar clusters → JSONB + relational fields

**Initialize database:**
```bash
alembic upgrade head
```

---

## Deployment

### Render Configuration

The project is designed for deployment on Render:
- **Web Service**: FastAPI server
- **Worker Service**: Background job processing
- **Cron Service**: Daily Slack updates
- **PostgreSQL Database**: Data persistence

Set environment variables in Render dashboard.

---

## Support

For issues and questions, contact the Mochi team.

## License

Proprietary - All rights reserved
