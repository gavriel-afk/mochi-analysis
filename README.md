# Mochi Analytics v2.0

Modern analytics platform for Mochi conversation data with FastAPI backend, PostgreSQL storage, and comprehensive analysis features.

## Features

- **6 Analysis Features**: Core metrics, setter analysis, time series, script clustering, objection classification, avatar clustering
- **4 Export Formats**: JSON, CSV (Framer CMS), PNG charts, Slack Block Kit
- **External Integrations**: Mochi API, Airtable, Slack, Framer CMS, Google Gemini
- **Database-First Storage**: PostgreSQL (solves Render ephemeral filesystem issue)
- **Daily Slack Digests**: Timezone-aware automated reporting
- **REST API**: FastAPI with async job processing
- **CLI Tool**: Command-line interface for local operations

## Project Structure

```
mochi-analytics/
├── src/mochi_analytics/
│   ├── core/              # Analysis engine
│   ├── storage/           # Database models
│   ├── api/               # FastAPI server
│   ├── workers/           # Background jobs
│   ├── exporters/         # Export formats
│   ├── integrations/      # External APIs
│   └── cli/               # CLI tool
├── config/                # Configuration files
├── tests/                 # Test suite
├── requirements/          # Dependencies
└── alembic/              # Database migrations
```

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL (or SQLite for local development)
- Git

### Installation

1. Clone the repository:
```bash
git clone <repo-url>
cd mochi-analytics
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements/dev.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and credentials
```

5. Initialize database:
```bash
alembic upgrade head
```

## Usage

### CLI Commands

```bash
# Run analysis
python -m mochi_analytics.cli analyze \
  --org-id <org-uuid> \
  --date-from 2025-01-01 \
  --date-to 2025-01-07 \
  --output analysis.json

# Start API server
python -m mochi_analytics.cli serve --port 8000

# Run background worker
python -m mochi_analytics.cli worker

# Run daily updates scheduler
python -m mochi_analytics.cli daily-updates
```

### API Endpoints

```bash
# Health check
GET /health

# Submit analysis job
POST /api/v1/analysis
Body: {conversations: [...], config: {...}}

# Get job status
GET /api/v1/analysis/{job_id}

# Export results
GET /api/v1/exports/{job_id}/json
GET /api/v1/exports/{job_id}/csv
GET /api/v1/exports/{job_id}/zip
GET /api/v1/exports/{job_id}/charts/{chart_id}.png
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/mochi_analytics --cov-report=html

# Run specific test file
pytest tests/unit/test_metrics.py -v
```

### Code Quality

```bash
# Linting
ruff check src/

# Type checking
mypy src/

# Format code
ruff format src/
```

## Deployment

### Render Configuration

The project includes `render.yaml` for easy deployment to Render:

- **Web Service**: FastAPI server
- **Worker Service**: Background job processing
- **Cron Service**: Daily Slack updates (runs hourly)
- **PostgreSQL Database**: Data persistence

### Environment Variables

Set these in Render dashboard:
- `MOCHI_SESSION_ID`
- `GOOGLE_API_KEY`
- `AIRTABLE_API_KEY`
- `AIRTABLE_BASE_ID`
- `SLACK_BOT_TOKEN`
- `FRAMER_API_URL`

## Architecture

### Database-First Storage

All data stored in PostgreSQL (no ephemeral filesystem):
- Analysis results → JSONB field
- Chart PNGs → Base64 TEXT field
- Reports → JSONB field
- Avatar clusters → JSONB + relational fields

### Daily Slack Digest

- Cron runs every hour
- Checks which orgs are due based on timezone + schedule_time
- Runs simplified analysis (core metrics + setters only)
- Sends Block Kit message to configured Slack channel

### Analysis Features

1. **Core Metrics**: Conversations, messages, reply rates, stage changes
2. **Setter Analysis**: Per-setter performance (2 modes: by sender, by assignment)
3. **Time Series**: Daily stage changes, activity by time of day (8 bins)
4. **Script Analysis**: RapidFuzz clustering + Gemini categorization
5. **Objection Classification**: Gemini batch classification (7 categories)
6. **Avatar Clustering**: Gemini embeddings + K-means (5 personas)

## License

Proprietary - All rights reserved

## Support

For issues and questions, contact the Mochi team.
