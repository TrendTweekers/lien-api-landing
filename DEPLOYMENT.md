# Deployment Guide

## Backend API Deployment

### Option 1: Railway (Easiest - Free Tier)

1. **Sign up**: [railway.app](https://railway.app)
2. **Create Project**: Click "New Project"
3. **Deploy from GitHub**:
   - Connect your GitHub repo
   - Select the `api/` folder
   - Railway auto-detects Python
4. **Get URL**: Railway gives you `https://your-app.railway.app`
5. **Update Landing Page**: Change API URL in `script.js`:
   ```javascript
   const response = await fetch('https://your-app.railway.app/v1/calculate', {
   ```

**Cost**: $0/month (500 hours free)

### Option 2: Vercel (Serverless)

1. Install Vercel CLI:
   ```bash
   npm i -g vercel
   ```

2. In `api/` directory:
   ```bash
   vercel
   ```

3. Follow prompts

**Cost**: $0/month (serverless free tier)

### Option 3: Render

1. Sign up: [render.com](https://render.com)
2. New Web Service
3. Connect GitHub repo
4. Set:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

**Cost**: $0/month (free tier available)

## Frontend Landing Page Deployment

### Vercel (Recommended)

1. **Install Vercel CLI**:
   ```bash
   npm i -g vercel
   ```

2. **In project root**:
   ```bash
   vercel
   ```

3. **Follow prompts** - Vercel auto-detects static site

4. **Get URL**: `https://your-site.vercel.app`

**Cost**: $0/month (unlimited static hosting)

### Netlify

1. Sign up: [netlify.com](https://netlify.com)
2. Drag & drop your project folder
3. Done!

**Cost**: $0/month

### GitHub Pages

1. Push to GitHub
2. Settings → Pages
3. Select `main` branch
4. Done!

**Cost**: $0/month

## Environment Variables

### Backend (Railway/Render)

No environment variables needed for MVP!

### Frontend

No environment variables needed - API URL is hardcoded in `script.js`

## Testing Deployment

### Test Backend

```bash
curl -X POST "https://your-api.railway.app/v1/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_date": "2024-11-01",
    "state": "TX",
    "role": "supplier"
  }'
```

### Test Frontend

1. Visit your deployed landing page
2. Use API tester
3. Should connect to your Railway backend

## Custom Domain (Optional)

### Backend (Railway)

1. Railway Dashboard → Settings → Domains
2. Add custom domain: `api.liendeadline.com`
3. Update DNS records

### Frontend (Vercel)

1. Vercel Dashboard → Project → Settings → Domains
2. Add custom domain: `liendeadline.com`
3. Update DNS records

## Monitoring

### Railway

- Built-in logs
- Metrics dashboard
- Free tier includes basic monitoring

### Vercel

- Built-in analytics
- Real-time logs
- Performance monitoring

## Cost Summary

**Total Monthly Cost: $0**

- Backend (Railway): $0
- Frontend (Vercel): $0
- Domain (optional): ~$12/year

## Next Steps After Deployment

1. ✅ Test API endpoint
2. ✅ Test landing page API tester
3. ✅ Add more states to `LIEN_RULES`
4. ✅ Set up monitoring/alerts
5. ✅ Add custom domain (optional)

