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
        
        # Get CTA patterns to avoid
        placement = self.config.get('placement', {})
        cta_patterns = placement.get('cta_patterns', [])
        
        # Build target keyword map from knowledge_graph
        target_keywords = self._build_keyword_map()
        
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
            
            # Detect permit opportunities (for ALL page types except excluded)
            permit_result = self._analyze_permit_opportunity(
                url, page_type, content_text, existing_links
            )
            if permit_result:
                all_permits.append(permit_result)
            
            # Architecture analysis (for ALL pages)
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
            
            # Skip money pages from linking TO other money pages (but permit/arch already done)
            if page_type == 'money_page':
                continue
            
            # Find keyword-based opportunities
            content_lower = content_text.lower()
            suggestions_for_page = 0
            max_per_page = self.config.get('limits', {}).get('max_links_per_page', 2)
            
            for target_url, keywords in target_keywords.items():
                # Skip if already linked
                normalized_target = self.architect.normalize_url(target_url)
                already_linked = any(
                    self.architect.normalize_url(link) == normalized_target 
                    for link in existing_links
                )
                if already_linked:
                    continue
                
                # Don't link to self
                if self.architect.normalize_url(url) == normalized_target:
                    continue
                
                # Check if any keyword appears in content
                for keyword in keywords:
                    keyword_lower = keyword.lower()
                    
                    if keyword_lower in content_lower:
                        # Check it's not in a CTA
                        is_cta = any(cta.lower() in keyword_lower or keyword_lower in cta.lower() 
                                    for cta in cta_patterns)
                        if is_cta:
                            continue
                        
                        # Find position in original text
                        pos = content_lower.find(keyword_lower)
                        context_start = max(0, pos - 50)
                        context_end = min(len(content_text), pos + len(keyword) + 50)
                        context = content_text[context_start:context_end]
                        
                        # Get target info
                        target_info = self._get_target_info(target_url)
                        target_title = target_info.get('title', target_url)
                        
                        # Calculate confidence
                        confidence = 0.70
                        campaigns = self.config.get('active_campaigns', {})
                        campaign_match = None
                        
                        if campaigns.get('primary', '') in target_url.lower():
                            confidence += 0.15
                            campaign_match = campaigns.get('primary')
                        elif campaigns.get('secondary', '') in target_url.lower():
                            confidence += 0.10
                            campaign_match = campaigns.get('secondary')
                        
                        suggestion = {
                            'source_url': url,
                            'source_title': title,
                            'target_url': target_url,
                            'target_type': 'money_page',
                            'suggested_anchor': keyword,
                            'paragraph_context': f"...{context}...",
                            'confidence_score': confidence,
                            'decision_reason': f"Keyword '{keyword}' found in content",
                            'campaign_alignment': campaign_match,
                            'source_type': page_type,
                            'action': 'PENDING'
                        }
                        
                        all_suggestions.append(suggestion)
                        suggestions_for_page += 1
                        
                        if suggestions_for_page >= max_per_page:
                            break
                
                if suggestions_for_page >= max_per_page:
                    break
        
        return {
            'suggestions': all_suggestions,
            'permits': all_permits,
            'architecture': all_architecture,
            'draft_payloads': []
        }
    
    def _build_keyword_map(self) -> Dict[str, List[str]]:
        """Build map of target URLs to their keywords."""
        kg = self.config.get('knowledge_graph', {})
        target_map = {}
        
        # Service hubs
        for name, hub in kg.get('service_hubs', {}).items():
            url = hub.get('url', '')
            keywords = hub.get('keywords', [])
            # Also add anchor pool keywords
            anchor_pool = self.config.get('anchor_pools', {}).get(name, [])
            all_keywords = keywords + anchor_pool
            target_map[url] = all_keywords
        
        # Materials
        for material in kg.get('materials', []):
            url = material.get('url', '')
            name = material.get('name', '')
            target_map[url] = [name.lower(), f"{name.lower()} pavers"]
        
        return target_map
    
    def _get_target_info(self, target_url: str) -> Dict[str, Any]:
        """Get info about a target URL from knowledge graph."""
        kg = self.config.get('knowledge_graph', {})
        
        for name, hub in kg.get('service_hubs', {}).items():
            if hub.get('url') == target_url:
                return hub
        
        return {'title': target_url}
    
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
