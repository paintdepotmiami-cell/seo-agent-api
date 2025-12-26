"""
SEO Intelligence Agent - Main Controller v2
Orchestrates: Config → Crawler/Cache → Engine → Reports → (Optional) Drafts
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

import yaml

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import deep_merge_dicts, ensure_dir


@dataclass
class RunContext:
    """Runtime context for a single agent run."""
    project_name: str
    mode: str
    timestamp: str
    output_dir: str
    cache_dir: str


def load_yaml(path: str) -> Dict[str, Any]:
    """Load YAML file."""
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def load_config(project_path: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Load and merge global_rules.yaml + project.yaml
    Project values override global defaults.
    """
    # Find paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(project_path)))
    global_path = os.path.join(base_dir, 'global_rules.yaml')
    project_yaml = os.path.join(project_path, 'project.yaml')
    
    if not os.path.exists(project_yaml):
        raise FileNotFoundError(f"Project config not found: {project_yaml}")
    
    # Load configs
    global_cfg = load_yaml(global_path) if os.path.exists(global_path) else {}
    project_cfg = load_yaml(project_yaml)
    
    # Merge
    merged = deep_merge_dicts(global_cfg, project_cfg)
    
    # Defensive defaults
    merged.setdefault('api', {})
    merged['api'].setdefault('mode', 'read_only')
    
    return project_cfg, merged


def run_with_cache(ctx: RunContext, config: Dict, cache_path: str) -> Dict[str, Any]:
    """Run analysis using cached page data."""
    from site_architect import SiteArchitect
    from anchor_validator import AnchorValidator
    from opportunity_engine import OpportunityEngine
    
    print(f"📦 Loading cache: {cache_path}")
    with open(cache_path, 'r', encoding='utf-8') as f:
        pages_data = json.load(f)
    
    print(f"🔍 Analyzing {len(pages_data)} pages...")
    
    # Initialize modules
    project_cfg, global_cfg = config, config  # Already merged
    architect = SiteArchitect(project_cfg, global_cfg)
    validator = AnchorValidator(global_cfg)
    engine = OpportunityEngine(project_cfg, global_cfg, architect, validator)
    
    # Analyze each page
    all_suggestions = []
    all_permits = []
    all_architecture = []
    
    for page in pages_data:
        url = page.get('url', '')
        title = page.get('title', 'Untitled')
        content_html = page.get('content_html', '')
        content_text = page.get('content_text', '')
        existing_links = page.get('existing_links', [])
        
        if not content_text:
            from utils import extract_text_from_html
            content_text = extract_text_from_html(content_html)
        
        # Classify page
        page_type, subtype, metadata = architect.classify_page(url)
        
        # Skip excluded
        if page_type == 'excluded':
            continue
        
        # Find opportunities
        opportunities = engine.find_opportunities(
            source_url=url,
            source_title=title,
            content_text=content_text,
            content_html=content_html,
            existing_links=existing_links
        )
        
        for opp in opportunities:
            opp_dict = opp.to_dict()
            opp_dict['action'] = 'PENDING'
            all_suggestions.append(opp_dict)
        
        # Architecture analysis
        all_architecture.append({
            'url': url,
            'page_type': page_type,
            'click_depth': page.get('depth', 2),
            'inbound_links': page.get('inbound_count', 0),
            'outbound_links': len(existing_links),
            'hub_score': 'High' if len(existing_links) >= 3 else 'Low',
            'status': 'NEEDS_LINKS' if page_type == 'money_page' and len(existing_links) < 2 else 'OK'
        })
    
    return {
        'suggestions': all_suggestions,
        'permits': all_permits,
        'architecture': all_architecture,
        'draft_payloads': []
    }


def main():
    parser = argparse.ArgumentParser(
        description='SEO Intelligence Agent - Internal Linking Automation'
    )
    parser.add_argument(
        '--project',
        required=True,
        help='Path to project directory (contains project.yaml)'
    )
    parser.add_argument(
        '--mode',
        choices=['read_only', 'apply_draft'],
        default=None,
        help='Execution mode (default: from config)'
    )
    parser.add_argument(
        '--use-cache',
        action='store_true',
        help='Use cached crawl data instead of calling WordPress'
    )
    parser.add_argument(
        '--cache-file',
        default=None,
        help='Path to cache JSON file'
    )
    parser.add_argument(
        '--output',
        default='./reports',
        help='Output directory for reports'
    )
    parser.add_argument(
        '--test-connection',
        action='store_true',
        help='Only test WordPress connection'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Generate sample data without WP connection'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔗 SEO INTELLIGENCE AGENT v2.0")
    print("=" * 60)
    
    # Load config
    print("\n📂 Loading configuration...")
    project_path = args.project
    
    try:
        project_cfg, merged_cfg = load_config(project_path)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1
    
    site_name = merged_cfg.get('site', {}).get('name', 'Unknown')
    site_url = merged_cfg.get('site', {}).get('url', '')
    run_mode = args.mode or merged_cfg.get('api', {}).get('mode', 'read_only')
    
    print(f"   Project: {site_name}")
    print(f"   Site: {site_url}")
    print(f"   Mode: {run_mode}")
    
    # Setup context
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    project_name = site_name.lower().replace(' ', '_').replace('&', 'and')
    output_dir = os.path.join(args.output, project_name, timestamp)
    cache_dir = os.path.join(os.path.dirname(project_path), '..', 'cache')
    
    ensure_dir(output_dir)
    ensure_dir(cache_dir)
    
    ctx = RunContext(
        project_name=project_name,
        mode=run_mode,
        timestamp=timestamp,
        output_dir=output_dir,
        cache_dir=cache_dir
    )
    
    print(f"   Output: {ctx.output_dir}\n")
    
    # Run analysis
    if args.dry_run:
        print("🧪 Dry run mode - using sample data...")
        analysis_data = {
            'suggestions': [
                {
                    'source_url': '/blog/travertine-guide/',
                    'source_title': 'Complete Travertine Paver Guide',
                    'target_url': '/driveways-miami/',
                    'target_type': 'money_page',
                    'suggested_anchor': 'driveway installation in Miami',
                    'paragraph_context': '...considering travertine for your driveway...',
                    'confidence_score': 0.92,
                    'decision_reason': 'Topical match + Campaign boost (driveways)',
                    'campaign_alignment': 'driveways',
                    'action': 'PENDING'
                },
                {
                    'source_url': '/blog/travertine-guide/',
                    'source_title': 'Complete Travertine Paver Guide',
                    'target_url': '/pool-deck-pavers-miami/',
                    'target_type': 'money_page',
                    'suggested_anchor': 'pool deck paver installation',
                    'paragraph_context': '...travertine is ideal for pool decks...',
                    'confidence_score': 0.78,
                    'decision_reason': 'Topical match',
                    'campaign_alignment': 'pool_decks',
                    'action': 'PENDING'
                },
                {
                    'source_url': '/projects/coral-gables-renovation/',
                    'source_title': 'Coral Gables Full Renovation',
                    'target_url': '/artificial-turf-installation-miami/',
                    'target_type': 'money_page',
                    'suggested_anchor': 'synthetic grass for backyards',
                    'paragraph_context': '...we also installed turf in the backyard...',
                    'confidence_score': 0.65,
                    'decision_reason': 'Keyword mention',
                    'campaign_alignment': 'turf',
                    'action': 'PENDING'
                }
            ],
            'permits': [
                {
                    'source_url': '/blog/driveway-installation-process/',
                    'source_type': 'blog_post',
                    'anchor_used': 'local permit approval process',
                    'permit_target': '/service-areas-map/',
                    'permit_decision': 'hub_fallback',
                    'geo_context_detected': None,
                    'fallback_used': True,
                    'confidence': 0.91
                },
                {
                    'source_url': '/projects/miami-beach-pool/',
                    'source_type': 'project',
                    'anchor_used': 'permit requirements in Miami Beach',
                    'permit_target': '/city-of-miami-beach-pavers-permit/',
                    'permit_decision': 'approved',
                    'geo_context_detected': 'Miami Beach',
                    'fallback_used': False,
                    'confidence': 0.95
                }
            ],
            'architecture': [
                {'url': '/driveways-miami/', 'page_type': 'money_page', 'click_depth': 1, 'inbound_links': 15, 'outbound_links': 5, 'hub_score': 'High', 'status': 'OK'},
                {'url': '/pool-deck-pavers-miami/', 'page_type': 'money_page', 'click_depth': 1, 'inbound_links': 8, 'outbound_links': 3, 'hub_score': 'Medium', 'status': 'OK'},
                {'url': '/blog/orphan-post/', 'page_type': 'blog', 'click_depth': 4, 'inbound_links': 0, 'outbound_links': 2, 'hub_score': 'Low', 'status': 'NEEDS_LINKS'},
                {'url': '/service-areas-map/', 'page_type': 'hub', 'click_depth': 1, 'inbound_links': 12, 'outbound_links': 9, 'hub_score': 'High', 'status': 'OK'}
            ],
            'draft_payloads': []
        }
    elif args.use_cache:
        cache_file = args.cache_file or os.path.join(cache_dir, f"{project_name}_pages.json")
        if not os.path.exists(cache_file):
            print(f"❌ Cache not found: {cache_file}")
            print("   Run without --use-cache first, or provide --cache-file")
            return 1
        analysis_data = run_with_cache(ctx, merged_cfg, cache_file)
    else:
        print("🌐 WordPress connection required...")
        print("   Please provide credentials in .env file")
        print("   Or use --dry-run for sample data")
        return 1
    
    # Generate reports
    print("\n📊 Generating reports...")
    from report_generator import ReportGenerator
    
    reporter = ReportGenerator(ctx.project_name, analysis_data)
    reporter.output_dir = ctx.output_dir
    reporter.generate_all()
    
    # Save raw JSON
    raw_path = os.path.join(ctx.output_dir, "analysis_raw.json")
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(analysis_data, f, ensure_ascii=False, indent=2)
    print(f"   ✅ analysis_raw.json")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"\n📈 Results:")
    print(f"   • {len(analysis_data.get('suggestions', []))} link opportunities")
    print(f"   • {len(analysis_data.get('permits', []))} permit validations")
    print(f"   • {len(analysis_data.get('architecture', []))} pages analyzed")
    print(f"\n📁 Reports: {ctx.output_dir}")
    print(f"   • dashboard.html (open in browser)")
    print(f"   • action_checklist.md")
    print(f"   • CSVs for detailed analysis")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
