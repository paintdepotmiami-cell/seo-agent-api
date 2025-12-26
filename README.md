# SEO Intelligence Agent API

Multi-tenant internal linking automation as a SaaS API.

## Quick Start (Local)

```bash
# Step 0: Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Step 1: Install dependencies
pip install -r requirements.txt

# Step 2: Run server
python server.py

# Step 3: Open in browser
# http://localhost:8000/analyze-preview/pavers_miami
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/projects` | GET | List available projects |
| `/analyze-preview/{project}` | GET | Interactive HTML Dashboard |
| `/analyze-json/{project}` | GET | Raw JSON data |
| `/cache/clear` | POST | Clear memory cache |

## Deploy to Render

1. Create GitHub repo
2. Push code
3. Connect to Render via Blueprints
4. `render.yaml` handles auto-configuration

```bash
git init
git add .
git commit -m "Deploy: SEO Agent API v2"
git remote add origin https://github.com/USER/seo-agent-api.git
git push -u origin main
```

## Project Structure

```
seo-agent-api/
├── render.yaml              # Render infrastructure
├── requirements.txt         # Dependencies
├── server.py               # FastAPI server
├── .gitignore
├── config/
│   ├── global_rules.yaml   # Universal SEO rules
│   └── projects/
│       └── pavers_miami.yaml
└── src/
    ├── __init__.py
    ├── config_loader.py    # Config fusion (deep merge)
    ├── cache_manager.py    # In-memory TTL cache
    ├── crawler.py          # WP REST API read
    ├── wp_client.py        # WP REST API write
    ├── engine.py           # Analysis orchestrator
    ├── intelligence.py     # Anchor/placement rules
    ├── report_generator.py # Dashboard HTML
    └── utils.py
```

## Adding New Projects

1. Create `config/projects/new_client.yaml`
2. Access: `/analyze-preview/new_client`

## Response Headers (Observability)

```
X-Cache: HIT | MISS
X-Exec-Time-Ms: 234.56
X-Items-Analyzed: 45
X-Run-ID: abc123
```
