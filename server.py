from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
import uvicorn
import os
import shutil
import uuid
import time
import logging

# Configuración de Logs para Render
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("seo-agent")

# Imports del Sistema
from src.config_loader import ConfigLoader
from src.cache_manager import memory_cache
from src.crawler import WPCrawler
from src.engine import SEOEngine
from src.report_generator import ReportGenerator
from src.wp_client import WPClient

from pydantic import BaseModel
from typing import List, Dict, Any
from fastapi import Request

app = FastAPI(title="SEO Intelligence API (SaaS Edition)")

# --- MODELO DE DATOS ---
class ChangeRequest(BaseModel):
    post_id: int
    changes: List[Dict[str, Any]] # Lista de cambios [{type: 'link', ...}]
    mode: str = "draft" # Por seguridad, default a draft

def run_analysis_logic(project_name: str, max_items: int):
    """Orquesta la lógica de negocio"""
    cfg = ConfigLoader.load(project_name)
    
    # 1. Crawl
    crawler = WPCrawler(cfg, max_items=max_items)
    pages_data = crawler.fetch_all()
    
    # 2. Analyze
    engine = SEOEngine(cfg)
    results = engine.run(pages_data)
    
    return results, len(pages_data)

@app.get("/")
def health_check():
    return {"status": "operational", "platform": "Render Paid", "workers": 4}

@app.get("/analyze-preview/{project_name}", response_class=HTMLResponse)
async def analyze_preview(project_name: str, max_items: int = Query(default=500, le=1000)):
    start_time = time.time()
    run_id = str(uuid.uuid4())
    # Directorio temporal único por petición para evitar colisiones
    temp_dir = f"reports_temp/{project_name}_{run_id}"
    
    try:
        # A. Verificar Caché
        cache_key = f"preview_{project_name}"
        cached_html = memory_cache.get(cache_key)
        
        if cached_html:
            exec_time = (time.time() - start_time) * 1000
            logger.info(f"⚡ CACHE HIT: {project_name} ({exec_time:.2f}ms)")
            return HTMLResponse(
                content=cached_html, 
                headers={
                    "X-Cache": "HIT",
                    "X-Exec-Time-Ms": f"{exec_time:.2f}"
                }
            )

        # B. Ejecución Real (Cache Miss)
        logger.info(f"🐢 STARTING ANALYSIS: {project_name}")
        
        analysis_data, items_count = run_analysis_logic(project_name, max_items=max_items)

        # C. Generación de Reporte
        os.makedirs(temp_dir, exist_ok=True)
        rg = ReportGenerator(project_name, analysis_data)
        rg.output_dir = temp_dir
        rg.generate_all()

        dashboard_path = os.path.join(temp_dir, "dashboard.html")
        with open(dashboard_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # D. Guardar en Caché
        memory_cache.set(cache_key, html_content)
        
        exec_time = (time.time() - start_time) * 1000
        logger.info(f"✅ ANALYSIS DONE: {items_count} items in {exec_time:.2f}ms")

        return HTMLResponse(
            content=html_content, 
            headers={
                "X-Cache": "MISS",
                "X-Exec-Time-Ms": f"{exec_time:.2f}",
                "X-Items-Analyzed": str(items_count),
                "X-Run-ID": run_id
            }
        )

    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis Failed: {str(e)}")

    finally:
        # E. Limpieza Robusta (Se ejecuta SIEMPRE, haya error o no)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

# Add cache clear endpoint for debugging
@app.post("/cache/clear")
async def clear_cache():
    """Clear all cached data."""
    if hasattr(memory_cache, 'clear'):
        count = memory_cache.clear()
        return {"cleared": count, "status": "ok"}
    # Fallback if method doesn't exist
    memory_cache._storage = {}
    return {"cleared": "all", "status": "ok"}

# Add analyze-json endpoint for debugging integration
@app.get("/analyze-json/{project_name}")
async def analyze_json(project_name: str, max_items: int = Query(default=500)):
    try:
        analysis_data, items_count = run_analysis_logic(project_name, max_items)
        return {
            "project": project_name,
            "items_analyzed": items_count,
            "data": analysis_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINT POST ---
@app.post("/apply-changes/{project_name}")
async def apply_changes_endpoint(project_name: str, payload: ChangeRequest, request: Request):
    # 1. Seguridad: Verificar API Key propia (definida en Render)
    api_key = request.headers.get("X-API-KEY")
    internal_key = os.environ.get("ADMIN_API_KEY", "local-dev-key")
    
    if api_key != internal_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    try:
        cfg = ConfigLoader.load(project_name)
        client = WPClient(cfg)
        
        result = client.apply_changes(
            post_id=payload.post_id,
            changes=payload.changes,
            status=payload.mode
        )
        
        return result

    except Exception as e:
        logger.error(f"Write failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Configuración local para pruebas
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
