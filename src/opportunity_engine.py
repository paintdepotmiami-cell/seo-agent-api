"""
SEO Intelligence Agent - Opportunity Engine
Detects and scores internal linking opportunities.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re


class LinkType(Enum):
    """Types of internal links."""
    SERVICE = "service"       # Link to money page
    PERMIT_HUB = "permit_hub" # Link to main permit hub
    PERMIT_CITY = "permit_city"  # Link to city-specific permit
    MATERIAL = "material"     # Link to material page
    BLOG = "blog"            # Link to blog post


@dataclass
class LinkOpportunity:
    """A detected internal linking opportunity."""
    source_url: str
    source_title: str
    target_url: str
    target_type: LinkType
    suggested_anchor: str
    paragraph_context: str      # ~50 chars around the anchor location
    sentence_context: str       # Full sentence containing the anchor
    confidence_score: float     # 0-1 score
    reasoning: str              # Why this link makes sense
    position_in_content: int    # Character offset in content
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_url': self.source_url,
            'source_title': self.source_title,
            'target_url': self.target_url,
            'target_type': self.target_type.value,
            'suggested_anchor': self.suggested_anchor,
            'paragraph_context': self.paragraph_context,
            'sentence_context': self.sentence_context,
            'confidence_score': round(self.confidence_score, 2),
            'reasoning': self.reasoning
        }


class OpportunityEngine:
    """
    Detects and prioritizes internal linking opportunities.
    - Semantic matching
    - Geo-context for permits
    - Campaign-aware scoring
    """
    
    def __init__(
        self, 
        project_config: Dict[str, Any], 
        global_rules: Dict[str, Any],
        site_architect,  # SiteArchitect instance
        anchor_validator  # AnchorValidator instance
    ):
        self.config = project_config
        self.global_rules = global_rules
        self.architect = site_architect
        self.validator = anchor_validator
        
        # Load scoring weights
        scoring = global_rules.get('scoring', {})
        self.weights = scoring.get('weights', {
            'topical_relevance': 0.30,
            'page_authority': 0.20,
            'content_age': 0.15,
            'existing_link_count': 0.15,
            'campaign_alignment': 0.20
        })
        self.min_score = scoring.get('thresholds', {}).get('min_score_to_suggest', 0.60)
        
        # Load campaign settings
        campaigns = project_config.get('active_campaigns', {})
        self.primary_campaign = campaigns.get('primary', '')
        self.secondary_campaign = campaigns.get('secondary', '')
        self.boost_multiplier = campaigns.get('boost_multiplier', 1.5)
    
    def find_opportunities(
        self,
        source_url: str,
        source_title: str,
        content_text: str,
        content_html: str,
        existing_links: List[str]
    ) -> List[LinkOpportunity]:
        """
        Find all linking opportunities in a piece of content.
        
        Args:
            source_url: URL of the page being analyzed
            source_title: Title of the source page
            content_text: Plain text content
            content_html: HTML content
            existing_links: URLs already linked from this page
            
        Returns:
            List of LinkOpportunity objects, sorted by confidence
        """
        opportunities = []
        
        # Skip excluded pages
        page_type, _, _ = self.architect.classify_page(source_url)
        if page_type == 'excluded':
            return []
        
        # Get max links allowed
        max_links = self.global_rules.get('limits', {}).get('max_links_per_page', 2)
        current_link_count = len(existing_links)
        
        if current_link_count >= max_links:
            return []  # Page already at limit
        
        slots_available = max_links - current_link_count
        
        # Find service page opportunities
        service_opps = self._find_service_opportunities(
            source_url, source_title, content_text, existing_links
        )
        opportunities.extend(service_opps)
        
        # Find permit opportunities (with geo-context)
        permit_opps = self._find_permit_opportunities(
            source_url, source_title, content_text, existing_links, page_type
        )
        opportunities.extend(permit_opps)
        
        # Score and sort
        for opp in opportunities:
            opp.confidence_score = self._calculate_score(opp, source_url)
        
        # Filter by minimum score
        opportunities = [o for o in opportunities if o.confidence_score >= self.min_score]
        
        # Sort by confidence (descending) and limit
        opportunities.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return opportunities[:slots_available]
    
    def _find_service_opportunities(
        self,
        source_url: str,
        source_title: str,
        content_text: str,
        existing_links: List[str]
    ) -> List[LinkOpportunity]:
        """Find opportunities to link to service pages."""
        opportunities = []
        kg = self.config.get('knowledge_graph', {})
        anchor_pools = self.config.get('anchor_pools', {})
        
        for service_key, service_data in kg.get('service_hubs', {}).items():
            target_url = service_data['url']
            
            # Skip if already linked
            if self.architect.normalize_url(target_url) in [
                self.architect.normalize_url(l) for l in existing_links
            ]:
                continue
            
            # Skip if linking to self
            if self.architect.normalize_url(source_url) == self.architect.normalize_url(target_url):
                continue
            
            # Find mention of service keywords in content
            for keyword in service_data.get('keywords', []):
                matches = self._find_keyword_in_content(content_text, keyword)
                
                for match_text, position, sentence in matches:
                    # Get best anchor from pool
                    pool = anchor_pools.get(service_key, [])
                    if not pool:
                        continue
                    
                    anchor_result = self.validator.get_best_anchor(
                        pool,
                        service_data.get('title', ''),
                        service_data.get('keywords', [''])[0]
                    )
                    
                    if anchor_result:
                        anchor, _ = anchor_result
                        
                        # Check if anchor text exists in content
                        if anchor.lower() in content_text.lower():
                            opp = LinkOpportunity(
                                source_url=source_url,
                                source_title=source_title,
                                target_url=target_url,
                                target_type=LinkType.SERVICE,
                                suggested_anchor=anchor,
                                paragraph_context=match_text[:100],
                                sentence_context=sentence,
                                confidence_score=0.0,  # Calculated later
                                reasoning=f"Content mentions '{keyword}', relevant to {service_key}",
                                position_in_content=position
                            )
                            opportunities.append(opp)
                            break  # One opp per service
        
        return opportunities
    
    def _find_permit_opportunities(
        self,
        source_url: str,
        source_title: str,
        content_text: str,
        existing_links: List[str],
        source_page_type: str
    ) -> List[LinkOpportunity]:
        """Find opportunities to link to permit pages with geo-context."""
        opportunities = []
        
        permit_rules = self.config.get('permit_rules', {})
        
        # Check if source is allowed to link to permits
        allowed_sources = permit_rules.get('allowed_sources', ['blog', 'money_page', 'project'])
        if source_page_type not in allowed_sources:
            return []
        
        # Check if source is a permit page (no permit-to-permit)
        if permit_rules.get('no_permit_to_permit', True):
            if source_page_type == 'permit_page':
                return []
        
        # Check existing permit links
        max_permit_links = self.global_rules.get('limits', {}).get('max_permit_links_per_page', 1)
        existing_permit_count = sum(
            1 for link in existing_links 
            if self.architect.is_permit_page(link)
        )
        
        if existing_permit_count >= max_permit_links:
            return []
        
        # Determine target: hub or specific city
        target_url, target_type, reasoning = self._determine_permit_target(content_text)
        
        if target_url:
            # Skip if already linked
            if self.architect.normalize_url(target_url) not in [
                self.architect.normalize_url(l) for l in existing_links
            ]:
                # Get anchor
                anchor_pools = self.config.get('anchor_pools', {})
                if target_type == LinkType.PERMIT_HUB:
                    pool = anchor_pools.get('permits_general', [])
                else:
                    pool = anchor_pools.get('permits_location_safe', [])
                
                if pool:
                    anchor = pool[0]  # Will be rotated by AnchorRotator
                    
                    opp = LinkOpportunity(
                        source_url=source_url,
                        source_title=source_title,
                        target_url=target_url,
                        target_type=target_type,
                        suggested_anchor=anchor,
                        paragraph_context="",
                        sentence_context="",
                        confidence_score=0.0,
                        reasoning=reasoning,
                        position_in_content=0
                    )
                    opportunities.append(opp)
        
        return opportunities
    
    def _determine_permit_target(
        self, 
        content_text: str
    ) -> Tuple[Optional[str], Optional[LinkType], str]:
        """
        Decide whether to link to hub or city-specific permit.
        
        Returns:
            Tuple of (target_url, link_type, reasoning)
        """
        permit_rules = self.config.get('permit_rules', {})
        hub_url = permit_rules.get('hub_url', '/service-areas-map/')
        
        # Check for geo-context requirement
        if not permit_rules.get('permit_link_requires_geo_context', True):
            return hub_url, LinkType.PERMIT_HUB, "Default to hub (no geo-context required)"
        
        # Look for city mentions in content
        geo_terms = permit_rules.get('geo_context_terms', [])
        content_lower = content_text.lower()
        
        found_city = None
        for term in geo_terms:
            if term.lower() in content_lower:
                found_city = term
                break
        
        if found_city:
            # Try to find matching permit page
            kg = self.config.get('knowledge_graph', {})
            authority = kg.get('authority_hubs', {})
            
            for permit in authority.get('permit_pages', []):
                if found_city.lower() in [t.lower() for t in permit.get('geo_terms', [])]:
                    return permit['url'], LinkType.PERMIT_CITY, f"Geo-context detected: {found_city}"
        
        # Default to hub (hub_priority rule)
        if permit_rules.get('hub_priority', True):
            return hub_url, LinkType.PERMIT_HUB, "Hub priority (no specific geo-context)"
        
        return None, None, ""
    
    def _find_keyword_in_content(
        self, 
        content: str, 
        keyword: str
    ) -> List[Tuple[str, int, str]]:
        """
        Find keyword mentions in content with context.
        
        Returns:
            List of (context_snippet, position, full_sentence)
        """
        results = []
        content_lower = content.lower()
        keyword_lower = keyword.lower()
        
        # Find all occurrences
        start = 0
        while True:
            pos = content_lower.find(keyword_lower, start)
            if pos == -1:
                break
            
            # Get surrounding context (50 chars each side)
            context_start = max(0, pos - 50)
            context_end = min(len(content), pos + len(keyword) + 50)
            context = content[context_start:context_end]
            
            # Get full sentence
            sentence_start = content.rfind('.', 0, pos)
            sentence_start = sentence_start + 1 if sentence_start != -1 else 0
            sentence_end = content.find('.', pos)
            sentence_end = sentence_end + 1 if sentence_end != -1 else len(content)
            sentence = content[sentence_start:sentence_end].strip()
            
            results.append((context, pos, sentence))
            start = pos + 1
        
        return results
    
    def _calculate_score(self, opportunity: LinkOpportunity, source_url: str) -> float:
        """Calculate confidence score for an opportunity."""
        score = 0.5  # Base score
        
        # Campaign alignment bonus
        target_type = opportunity.target_type
        if target_type == LinkType.SERVICE:
            # Check if target matches active campaign
            target_url = opportunity.target_url.lower()
            if self.primary_campaign.lower() in target_url:
                score += self.weights.get('campaign_alignment', 0.2) * self.boost_multiplier
            elif self.secondary_campaign.lower() in target_url:
                score += self.weights.get('campaign_alignment', 0.2)
        
        # Permit hub gets bonus for being central authority
        if target_type == LinkType.PERMIT_HUB:
            score += 0.1
        
        # Specific geo-match for permits
        if target_type == LinkType.PERMIT_CITY:
            score += 0.15  # Geo-context detected
        
        return min(score, 1.0)
