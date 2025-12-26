"""
SEO Intelligence Agent - Anchor Validator
Validates anchor text against exact-match rules and similarity thresholds.
"""

from difflib import SequenceMatcher
from typing import Tuple, Dict, Any, List, Optional
import re


class AnchorValidator:
    """
    Validates anchor text safety and rotation.
    - Prevents exact-match spam
    - Enforces similarity thresholds
    - Tracks anchor rotation to avoid repetition
    """
    
    def __init__(self, global_rules: Dict[str, Any]):
        self.rules = global_rules.get('anchor_rules', {})
        self.rotation_memory: List[str] = []
        self.memory_size = self.rules.get('rotation_memory', 3)
    
    def is_safe_anchor(
        self, 
        anchor_text: str, 
        target_title: str,
        target_primary_keyword: str,
        existing_anchors_on_page: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """
        Validate if anchor text is safe to use.
        
        Args:
            anchor_text: The proposed anchor text
            target_title: H1/title of the target page
            target_primary_keyword: Primary keyword of target page
            existing_anchors_on_page: Anchors already used on source page
            
        Returns:
            Tuple of (is_safe, reason)
        """
        anchor = anchor_text.lower().strip()
        
        # Length checks
        min_len = self.rules.get('min_anchor_length', 10)
        max_len = self.rules.get('max_anchor_length', 50)
        
        if len(anchor) < min_len:
            return False, f"Anchor too short (<{min_len} chars)"
        if len(anchor) > max_len:
            return False, f"Anchor too long (>{max_len} chars)"
        
        # Check exact match against target title
        if self.rules.get('no_exact_match_target_title', True):
            similarity = self._calculate_similarity(anchor, target_title.lower())
            threshold = self.rules.get('similarity_threshold', 0.85)
            
            if similarity > threshold:
                return False, f"Too similar to target title ({similarity:.0%})"
        
        # Check exact match against primary keyword
        if self.rules.get('no_exact_match_primary_keyword', True):
            similarity = self._calculate_similarity(anchor, target_primary_keyword.lower())
            threshold = self.rules.get('similarity_threshold', 0.85)
            
            if similarity > threshold:
                return False, f"Too similar to primary keyword ({similarity:.0%})"
        
        # Check rotation memory
        if anchor in self.rotation_memory:
            return False, f"Anchor used recently (within last {self.memory_size} uses)"
        
        # Check if already used on this page
        if existing_anchors_on_page:
            for existing in existing_anchors_on_page:
                if self._calculate_similarity(anchor, existing.lower()) > 0.9:
                    return False, "Similar anchor already on this page"
        
        return True, "Safe"
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity ratio between two strings (0-1)."""
        return SequenceMatcher(None, str1, str2).ratio()
    
    def record_anchor_use(self, anchor_text: str) -> None:
        """Record that an anchor was used for rotation tracking."""
        anchor = anchor_text.lower().strip()
        self.rotation_memory.append(anchor)
        
        # Keep only last N anchors
        if len(self.rotation_memory) > self.memory_size:
            self.rotation_memory.pop(0)
    
    def get_best_anchor(
        self,
        anchor_pool: List[str],
        target_title: str,
        target_primary_keyword: str,
        existing_anchors_on_page: Optional[List[str]] = None
    ) -> Optional[Tuple[str, str]]:
        """
        Select the best anchor from a pool.
        
        Returns:
            Tuple of (anchor_text, reason) or None if no safe anchor found
        """
        for anchor in anchor_pool:
            is_safe, reason = self.is_safe_anchor(
                anchor, 
                target_title, 
                target_primary_keyword,
                existing_anchors_on_page
            )
            if is_safe:
                return anchor, "Selected from pool"
        
        return None
    
    def validate_placement(
        self,
        anchor_text: str,
        surrounding_text: str,
        html_context: str
    ) -> Tuple[bool, str]:
        """
        Validate anchor placement in content.
        
        Args:
            anchor_text: The anchor to place
            surrounding_text: Text around the anchor position
            html_context: HTML tags surrounding the position
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check forbidden tags
        forbidden_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                         'title', 'figcaption', 'nav', 'footer', 'button']
        
        html_lower = html_context.lower()
        for tag in forbidden_tags:
            if f'<{tag}' in html_lower:
                return False, f"Cannot place in <{tag}> tag"
        
        # Check minimum surrounding context
        min_words = 5
        words_before = len(surrounding_text.split())
        if words_before < min_words:
            return False, f"Not enough context (need {min_words}+ words)"
        
        return True, "Valid placement"


class AnchorRotator:
    """
    Manages anchor pool rotation across multiple pages.
    Ensures diverse anchor usage across the site.
    """
    
    def __init__(self, anchor_pools: Dict[str, List[str]]):
        self.pools = anchor_pools
        self.usage_counts: Dict[str, Dict[str, int]] = {}
        
        # Initialize usage counts
        for category, anchors in anchor_pools.items():
            self.usage_counts[category] = {a: 0 for a in anchors}
    
    def get_next_anchor(self, category: str) -> Optional[str]:
        """
        Get the least-used anchor from a category.
        
        Args:
            category: The anchor pool category (e.g., 'driveways', 'permits_general')
            
        Returns:
            Anchor text with lowest usage count, or None if category not found
        """
        if category not in self.usage_counts:
            return None
        
        # Find anchor with lowest usage
        min_count = min(self.usage_counts[category].values())
        for anchor, count in self.usage_counts[category].items():
            if count == min_count:
                return anchor
        
        return None
    
    def record_usage(self, category: str, anchor: str) -> None:
        """Record that an anchor from a category was used."""
        if category in self.usage_counts and anchor in self.usage_counts[category]:
            self.usage_counts[category][anchor] += 1
    
    def get_usage_stats(self) -> Dict[str, Dict[str, int]]:
        """Get current usage statistics for all anchors."""
        return self.usage_counts.copy()
