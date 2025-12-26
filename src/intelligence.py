"""
SEO Intelligence Agent - Intelligence Module
Anchor text rules, regex patterns, and semantic validation.
"""

from typing import List, Dict, Any, Tuple, Optional
from difflib import SequenceMatcher
import re


class AnchorIntelligence:
    """
    Intelligent anchor text selection and validation.
    Handles similarity checks, forbidden patterns, and rotation.
    """
    
    # Forbidden exact matches (case-insensitive)
    FORBIDDEN_EXACT = [
        'click here',
        'read more',
        'learn more',
        'this page',
        'here',
    ]
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        anchor_rules = config.get('anchor_rules', {})
        
        self.similarity_threshold = anchor_rules.get('similarity_threshold', 0.85)
        self.min_length = anchor_rules.get('min_anchor_length', 10)
        self.max_length = anchor_rules.get('max_anchor_length', 50)
        self.no_exact_match_title = anchor_rules.get('no_exact_match_target_title', True)
        self.no_exact_match_keyword = anchor_rules.get('no_exact_match_primary_keyword', True)
    
    def is_valid_anchor(
        self,
        anchor: str,
        target_title: str,
        target_keyword: str
    ) -> Tuple[bool, str]:
        """
        Validate anchor text against all rules.
        
        Returns:
            Tuple of (is_valid, reason)
        """
        anchor_lower = anchor.lower().strip()
        
        # Length checks
        if len(anchor_lower) < self.min_length:
            return False, f"Too short (min {self.min_length})"
        
        if len(anchor_lower) > self.max_length:
            return False, f"Too long (max {self.max_length})"
        
        # Forbidden patterns
        for forbidden in self.FORBIDDEN_EXACT:
            if anchor_lower == forbidden:
                return False, f"Forbidden anchor: {forbidden}"
        
        # Similarity to title
        if self.no_exact_match_title:
            sim = self._similarity(anchor_lower, target_title.lower())
            if sim > self.similarity_threshold:
                return False, f"Too similar to title ({sim:.0%})"
        
        # Similarity to primary keyword
        if self.no_exact_match_keyword:
            sim = self._similarity(anchor_lower, target_keyword.lower())
            if sim > self.similarity_threshold:
                return False, f"Too similar to keyword ({sim:.0%})"
        
        return True, "Valid"
    
    def _similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity (0-1)."""
        return SequenceMatcher(None, s1, s2).ratio()
    
    def find_anchor_in_content(
        self,
        content: str,
        anchor: str
    ) -> Optional[Tuple[int, str]]:
        """
        Find anchor text in content with context.
        
        Returns:
            Tuple of (position, surrounding_context) or None
        """
        content_lower = content.lower()
        anchor_lower = anchor.lower()
        
        pos = content_lower.find(anchor_lower)
        if pos == -1:
            return None
        
        # Get context (50 chars each side)
        start = max(0, pos - 50)
        end = min(len(content), pos + len(anchor) + 50)
        context = content[start:end]
        
        return pos, context
    
    def select_best_anchor(
        self,
        pool: List[str],
        content: str,
        target_title: str,
        target_keyword: str,
        used_anchors: List[str] = None
    ) -> Optional[str]:
        """
        Select the best valid anchor from a pool.
        Prefers anchors that exist in content.
        """
        used = [a.lower() for a in (used_anchors or [])]
        
        # First pass: find anchors that exist in content
        for anchor in pool:
            if anchor.lower() in used:
                continue
            
            is_valid, _ = self.is_valid_anchor(anchor, target_title, target_keyword)
            if not is_valid:
                continue
            
            if anchor.lower() in content.lower():
                return anchor
        
        # Second pass: any valid anchor
        for anchor in pool:
            if anchor.lower() in used:
                continue
            
            is_valid, _ = self.is_valid_anchor(anchor, target_title, target_keyword)
            if is_valid:
                return anchor
        
        return None


class PlacementValidator:
    """
    Validates link placement within content.
    Ensures links don't appear in forbidden locations.
    """
    
    FORBIDDEN_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'title', 'figcaption']
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        placement = config.get('placement', {})
        self.forbidden = placement.get('forbidden_locations', self.FORBIDDEN_TAGS)
    
    def is_valid_placement(
        self,
        html: str,
        anchor: str,
        position: int
    ) -> Tuple[bool, str]:
        """
        Check if anchor position is valid.
        
        Returns:
            Tuple of (is_valid, reason)
        """
        # Extract surrounding HTML tags
        start = max(0, position - 100)
        end = min(len(html), position + len(anchor) + 100)
        context = html[start:end].lower()
        
        # Check for forbidden tags
        for tag in self.forbidden:
            if f'<{tag}' in context and f'</{tag}>' in context:
                return False, f"Inside <{tag}> tag"
        
        # Check for first paragraph
        if self._is_first_paragraph(html, position):
            return False, "In first paragraph"
        
        return True, "Valid"
    
    def _is_first_paragraph(self, html: str, position: int) -> bool:
        """Check if position is in the first paragraph."""
        # Find first <p> tag
        first_p = html.lower().find('<p')
        if first_p == -1:
            return False
        
        # Find closing </p>
        first_p_end = html.lower().find('</p>', first_p)
        if first_p_end == -1:
            return False
        
        return first_p <= position <= first_p_end


class GeoContextDetector:
    """
    Detects geographic context in content for permit linking.
    """
    
    def __init__(self, config: Dict[str, Any]):
        permit_rules = config.get('permit_rules', {})
        self.geo_terms = permit_rules.get('geo_context_terms', [])
    
    def detect_geo(self, content: str) -> Optional[str]:
        """
        Detect geographic mentions in content.
        
        Returns:
            Detected city/area or None
        """
        content_lower = content.lower()
        
        for term in self.geo_terms:
            if term.lower() in content_lower:
                return term
        
        return None
    
    def should_link_permit(
        self,
        content: str,
        source_type: str,
        existing_permit_links: int
    ) -> Tuple[bool, str, str]:
        """
        Determine if content should link to permit page.
        
        Returns:
            Tuple of (should_link, target_url, reason)
        """
        # Check source type
        allowed = ['blog', 'money_page', 'project']
        if source_type not in allowed:
            return False, '', 'Source type not allowed'
        
        # Check existing permit links
        max_permit = 1
        if existing_permit_links >= max_permit:
            return False, '', 'Already has permit link'
        
        # Detect geo
        geo = self.detect_geo(content)
        
        if geo:
            # Return city-specific permit URL
            return True, f'/city-of-{geo.lower().replace(" ", "-")}-permit/', f'Geo context: {geo}'
        
        # Default to hub
        return True, '/service-areas-map/', 'Hub fallback (no geo context)'
