# Lien Deadline API - Simple MVP Backend

This is a minimal FastAPI backend for calculating mechanics lien deadlines.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Locally

```bash
uvicorn main:app --reload
```

API will be available at: `http://localhost:8000`

### 3. Test It

```bash
curl -X POST "http://localhost:8000/v1/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_date": "2024-11-01",
    "state": "TX",
    "role": "supplier"
  }'
```

## Deployment

### Railway (Recommended - Free Tier)

1. Create account at [railway.app](https://railway.app)
2. New Project → Deploy from GitHub
3. Connect your repo
4. Railway auto-detects Python and runs `uvicorn main:app`
5. Get your URL: `https://your-app.railway.app`

### Vercel

```bash
pip install vercel
vercel
```

### Heroku

```bash
heroku create lien-api
git push heroku main
```

## Adding States

1. Research state lien law (1 hour per state)
2. Add to `LIEN_RULES` dict in `main.py`:

```python
"CA": {
    "preliminary_notice_days": 20,
    "lien_filing_days": 90,
    "serving": ["owner"]
}
```

3. Deploy update
4. Done!

## API Endpoints

### POST `/v1/calculate`

Calculate lien deadlines.

**Request:**
```json
{
  "invoice_date": "2024-11-01",
  "state": "TX",
  "role": "supplier"
}
```

**Response:**
```json
{
  "preliminary_notice_deadline": "2024-11-16",
  "lien_filing_deadline": "2025-01-30",
  "serving_requirements": ["owner", "gc"],
  "disclaimer": "Not legal advice..."
}
```

### GET `/v1/states`

Get list of supported states.

## Cost

- **Railway Free Tier**: $0/month (500 hours)
- **Vercel**: $0/month (serverless)
- **Heroku**: $0/month (free tier available)

## Time Investment

- **Initial Setup**: 30 minutes
- **Per State**: 1 hour (research + add to dict)
- **Total for 50 states**: ~50 hours

## Next Steps

1. Deploy to Railway
2. Update landing page API URL to your Railway URL
3. Test with real requests
4. Add states one at a time as customers request them

