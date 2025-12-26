"""
SEO Intelligence Agent - Core Engine
Orchestrates site analysis and opportunity detection.
"""

from typing import Dict, Any, List
import re

from site_architect import SiteArchitect
from anchor_validator import AnchorValidator, AnchorRotator
from opportunity_engine import OpportunityEngine


class SEOEngine:
    """
    Main analysis engine.
    Coordinates all intelligence modules.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.architect = SiteArchitect(config, config)
        self.validator = AnchorValidator(config)
        self.rotator = AnchorRotator(config.get('anchor_pools', {}))
        self.opportunity_engine = OpportunityEngine(
            config, config, self.architect, self.validator
        )
    
    def run(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run full site analysis.
        
        Args:
            pages_data: List of page data from crawler
            
        Returns:
            Analysis results dict with suggestions, permits, architecture
        """
        all_suggestions = []
        all_permits = []
        all_architecture = []
        
        # Track existing links across site
        site_links = {}
        
        for page in pages_data:
            url = page.get('url', '')
            title = page.get('title', 'Untitled')
            content_html = page.get('content_html', '')
            content_text = page.get('content_text', '')
            
            # Extract text if not provided
            if not content_text and content_html:
                content_text = self._extract_text(content_html)
            
            # Get existing internal links
            existing_links = page.get('existing_links', [])
            if not existing_links and content_html:
                existing_links = self._extract_links(content_html)
            
            site_links[url] = existing_links
            
            # Classify page
            page_type, subtype, metadata = self.architect.classify_page(url)
            
            # Skip excluded pages
            if page_type == 'excluded':
                continue
            
            # Find linking opportunities
            opportunities = self.opportunity_engine.find_opportunities(
                source_url=url,
                source_title=title,
                content_text=content_text,
                content_html=content_html,
                existing_links=existing_links
            )
            
            for opp in opportunities:
                opp_dict = opp.to_dict()
                opp_dict['source_type'] = page_type
                opp_dict['action'] = 'PENDING'
                
                # Determine campaign alignment
                if opp.target_type.value == 'service':
                    target_url = opp.target_url.lower()
                    campaigns = self.config.get('active_campaigns', {})
                    if campaigns.get('primary', '') in target_url:
                        opp_dict['campaign_alignment'] = campaigns.get('primary')
                    elif campaigns.get('secondary', '') in target_url:
                        opp_dict['campaign_alignment'] = campaigns.get('secondary')
                    else:
                        opp_dict['campaign_alignment'] = None
                else:
                    opp_dict['campaign_alignment'] = None
                
                # Add decision reason
                opp_dict['decision_reason'] = opp.reasoning
                
                all_suggestions.append(opp_dict)
            
            # Detect permit opportunities
            permit_result = self._analyze_permit_opportunity(
                url, page_type, content_text, existing_links
            )
            if permit_result:
                all_permits.append(permit_result)
            
            # Architecture analysis
            arch_entry = {
                'url': url,
                'page_type': page_type,
                'click_depth': page.get('depth', 2),
                'inbound_links': self._count_inbound(url, site_links),
                'outbound_links': len(existing_links),
                'hub_score': self._calculate_hub_score(page_type, len(existing_links)),
                'status': self._determine_status(page_type, len(existing_links))
            }
            all_architecture.append(arch_entry)
        
        return {
            'suggestions': all_suggestions,
            'permits': all_permits,
            'architecture': all_architecture,
            'draft_payloads': []
        }
    
    def _extract_text(self, html: str) -> str:
        """Extract plain text from HTML."""
        # Remove script/style
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove tags
        text = re.sub(r'<[^>]+>', ' ', html)
        return re.sub(r'\s+', ' ', text).strip()
    
    def _extract_links(self, html: str) -> List[str]:
        """Extract internal links from HTML."""
        site_url = self.config.get('site', {}).get('url', '')
        pattern = rf'href=["\']({re.escape(site_url)}[^"\']*|/[^"\']*)["\']'
        matches = re.findall(pattern, html)
        
        links = []
        for match in matches:
            if match.startswith('/'):
                links.append(match)
            else:
                links.append(match.replace(site_url, ''))
        return links
    
    def _analyze_permit_opportunity(
        self, 
        url: str, 
        page_type: str, 
        content_text: str,
        existing_links: List[str]
    ) -> Dict[str, Any] | None:
        """Check if page should link to permit hub."""
        permit_rules = self.config.get('permit_rules', {})
        
        # Check if source type is allowed
        allowed = permit_rules.get('allowed_sources', ['blog', 'money_page', 'project'])
        if page_type not in allowed:
            return None
        
        # Check for existing permit links
        for link in existing_links:
            if self.architect.is_permit_page(link):
                return None  # Already has permit link
        
        # Check for geo-context
        geo_terms = permit_rules.get('geo_context_terms', [])
        found_geo = None
        for term in geo_terms:
            if term.lower() in content_text.lower():
                found_geo = term
                break
        
        # Determine target
        if found_geo:
            # Find matching permit page
            kg = self.config.get('knowledge_graph', {})
            authority = kg.get('authority_hubs', {})
            for permit in authority.get('permit_pages', []):
                if found_geo.lower() in [t.lower() for t in permit.get('geo_terms', [])]:
                    return {
                        'source_url': url,
                        'source_type': page_type,
                        'anchor_used': f"permit requirements in {found_geo}",
                        'permit_target': permit['url'],
                        'permit_decision': 'approved',
                        'geo_context_detected': found_geo,
                        'fallback_used': False,
                        'confidence': 0.90
                    }
        
        # Default to hub
        hub_url = permit_rules.get('hub_url', '/service-areas-map/')
        return {
            'source_url': url,
            'source_type': page_type,
            'anchor_used': 'local permit approval process',
            'permit_target': hub_url,
            'permit_decision': 'hub_fallback',
            'geo_context_detected': None,
            'fallback_used': True,
            'confidence': 0.75
        }
    
    def _count_inbound(self, url: str, site_links: Dict[str, List[str]]) -> int:
        """Count inbound links to a URL."""
        count = 0
        normalized = self.architect.normalize_url(url)
        for source, links in site_links.items():
            for link in links:
                if self.architect.normalize_url(link) == normalized:
                    count += 1
        return count
    
    def _calculate_hub_score(self, page_type: str, link_count: int) -> str:
        """Calculate hub strength score."""
        if page_type in ['money_page', 'hub']:
            if link_count >= 5:
                return 'High'
            elif link_count >= 2:
                return 'Medium'
        return 'Low'
    
    def _determine_status(self, page_type: str, link_count: int) -> str:
        """Determine page status for architecture report."""
        if page_type == 'money_page' and link_count < 2:
            return 'NEEDS_LINKS'
        if link_count > 5:
            return 'OVER_LINKED'
        return 'OK'
