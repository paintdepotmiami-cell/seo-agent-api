"""
SEO Intelligence Agent - FastAPI Server
Production-ready API for Render deployment.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys
import shutil
import uuid
import time
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

# Logging configuration for Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("seo-agent")

# Late imports (after path setup)
from src.config_loader import ConfigLoader
from src.cache_manager import memory_cache
from src.crawler import WPCrawler
from src.engine import SEOEngine
from src.report_generator import ReportGenerator


app = FastAPI(
    title="SEO Intelligence API",
    description="Internal Linking Automation for WordPress",
    version="2.0.0"
)

# CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def run_analysis_logic(project_name: str, max_items: int):
    """Orchestrate the analysis pipeline."""
    cfg = ConfigLoader.load(project_name)
    
    # 1. Crawl WordPress
    crawler = WPCrawler(cfg, max_items=max_items)
    pages_data = crawler.fetch_all()
    
    # 2. Run analysis
    engine = SEOEngine(cfg)
    results = engine.run(pages_data)
    
    return results, len(pages_data)


@app.get("/")
def health_check():
    """Health check endpoint."""
    return {
        "status": "operational",
        "service": "SEO Intelligence Agent",
        "version": "2.0.0",
        "cache_stats": memory_cache.stats()
    }


@app.get("/projects")
def list_projects():
    """List available projects."""
    projects_dir = os.path.join(os.getcwd(), "config", "projects")
    
    if not os.path.exists(projects_dir):
        return {"projects": [], "error": "Projects directory not found"}
    
    projects = []
    for f in os.listdir(projects_dir):
        if f.endswith('.yaml'):
            projects.append(f.replace('.yaml', ''))
    
    return {"projects": projects}


@app.get("/analyze-preview/{project_name}", response_class=HTMLResponse)
async def analyze_preview(
    project_name: str, 
    max_items: int = Query(default=500, le=1000)
):
    """
    Run analysis and return interactive HTML dashboard.
    
    Args:
        project_name: Project config name (without .yaml)
        max_items: Maximum pages to analyze
    """
    start_time = time.time()
    run_id = str(uuid.uuid4())[:8]
    temp_dir = f"reports_temp/{project_name}_{run_id}"
    
    try:
        # A. Check cache
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
        
        # B. Run analysis (cache miss)
        logger.info(f"🔍 STARTING ANALYSIS: {project_name}")
        
        analysis_data, items_count = run_analysis_logic(project_name, max_items)
        
        # C. Generate report
        os.makedirs(temp_dir, exist_ok=True)
        rg = ReportGenerator(project_name, analysis_data)
        rg.output_dir = temp_dir
        rg.generate_all()
        
        # D. Read HTML
        dashboard_path = os.path.join(temp_dir, "dashboard.html")
        with open(dashboard_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        # E. Cache result
        memory_cache.set(cache_key, html_content, ttl=900)  # 15 min
        
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
    
    except FileNotFoundError as e:
        logger.error(f"❌ Config error: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    finally:
        # F. Cleanup (always runs)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@app.get("/analyze-json/{project_name}")
async def analyze_json(
    project_name: str,
    max_items: int = Query(default=500, le=1000)
):
    """
    Run analysis and return raw JSON results.
    
    Useful for integrations and automation.
    """
    start_time = time.time()
    
    try:
        # Check cache
        cache_key = f"json_{project_name}"
        cached_data = memory_cache.get(cache_key)
        
        if cached_data:
            return JSONResponse(
                content=cached_data,
                headers={"X-Cache": "HIT"}
            )
        
        # Run analysis
        analysis_data, items_count = run_analysis_logic(project_name, max_items)
        
        # Add metadata
        result = {
            "project": project_name,
            "items_analyzed": items_count,
            "exec_time_ms": (time.time() - start_time) * 1000,
            "data": analysis_data
        }
        
        # Cache
        memory_cache.set(cache_key, result, ttl=900)
        
        return JSONResponse(
            content=result,
            headers={"X-Cache": "MISS"}
        )
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:
        logger.error(f"❌ ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cache/clear")
async def clear_cache():
    """Clear all cached data."""
    count = memory_cache.clear()
    return {"cleared": count, "status": "ok"}


from pydantic import BaseModel
from typing import List, Optional

class LinkApproval(BaseModel):
    source_url: str
    target_url: str
    anchor_text: str
    link_type: str  # 'internal' or 'permit'

class ApplyRequest(BaseModel):
    project_name: str
    approved_links: List[LinkApproval]

@app.post("/apply-approved")
async def apply_approved(request: ApplyRequest):
    """
    Apply approved links to WordPress as drafts.
    
    Each approved link will be inserted into the source page content.
    Changes are saved as revisions (drafts), not published directly.
    """
    start_time = time.time()
    
    try:
        # Load config
        cfg = ConfigLoader.load(request.project_name)
        
        # Check mode
        api_mode = cfg.get('api', {}).get('mode', 'read_only')
        if api_mode != 'apply_draft':
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Agent is in read_only mode",
                    "message": "Change api.mode to 'apply_draft' in config to enable",
                    "current_mode": api_mode
                }
            )
        
        # Import wp_client
        from src.wp_client import WPClient
        wp = WPClient(cfg)
        
        # Test connection
        if not wp.test_connection():
            return JSONResponse(
                status_code=500,
                content={"error": "WordPress connection failed"}
            )
        
        results = {
            "total": len(request.approved_links),
            "success": 0,
            "failed": 0,
            "details": []
        }
        
        # Apply each link
        for link in request.approved_links:
            try:
                # Get post ID from URL
                post_id = get_post_id_from_url(cfg, link.source_url)
                
                if not post_id:
                    results["failed"] += 1
                    results["details"].append({
                        "source": link.source_url,
                        "status": "failed",
                        "reason": "Could not find post ID"
                    })
                    continue
                
                # Apply the link
                success = wp.apply_link(
                    post_id=post_id,
                    content_type='posts',  # Could be 'pages' too
                    anchor_text=link.anchor_text,
                    target_url=link.target_url,
                    as_draft=True
                )
                
                if success:
                    results["success"] += 1
                    results["details"].append({
                        "source": link.source_url,
                        "target": link.target_url,
                        "anchor": link.anchor_text,
                        "status": "applied_as_draft"
                    })
                else:
                    results["failed"] += 1
                    results["details"].append({
                        "source": link.source_url,
                        "status": "failed",
                        "reason": "wp.apply_link returned None"
                    })
                    
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "source": link.source_url,
                    "status": "error",
                    "reason": str(e)
                })
        
        results["exec_time_ms"] = (time.time() - start_time) * 1000
        
        # Clear cache after applying
        memory_cache.clear()
        
        return results
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Apply failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def get_post_id_from_url(cfg: dict, url: str) -> Optional[int]:
    """
    Get WordPress post/page ID from URL.
    Returns None if not found.
    """
    import requests
    
    site_url = cfg.get('site', {}).get('url', '').rstrip('/')
    api = cfg.get('api', {})
    
    # Normalize URL
    if url.startswith('/'):
        slug = url.strip('/').split('/')[-1]
    else:
        slug = url.replace(site_url, '').strip('/').split('/')[-1]
    
    # Try to find by slug
    try:
        auth = (api.get('username'), api.get('app_password'))
        
        # Try posts first
        resp = requests.get(
            f"{site_url}/wp-json/wp/v2/posts",
            params={'slug': slug},
            auth=auth,
            timeout=10
        )
        if resp.status_code == 200 and resp.json():
            return resp.json()[0].get('id')
        
        # Try pages
        resp = requests.get(
            f"{site_url}/wp-json/wp/v2/pages",
            params={'slug': slug},
            auth=auth,
            timeout=10
        )
        if resp.status_code == 200 and resp.json():
            return resp.json()[0].get('id')
            
    except Exception as e:
        logger.error(f"get_post_id_from_url error: {e}")
    
    return None


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
