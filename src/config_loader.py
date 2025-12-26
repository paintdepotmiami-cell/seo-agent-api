"""
SEO Intelligence Agent - Configuration Loader
Handles deep merge of global_rules.yaml + project.yaml
"""

import yaml
import os
import copy
from typing import Dict, Any


class ConfigLoader:
    """
    Loads and merges configuration files.
    Project config overrides global rules.
    """
    
    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge dictionaries without data loss."""
        result = copy.deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigLoader._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    @staticmethod
    def load(project_name: str) -> Dict[str, Any]:
        """
        Load merged configuration for a project.
        
        Args:
            project_name: Name of project (without .yaml extension)
            
        Returns:
            Merged configuration dictionary
        """
        # Use os.getcwd() for correct paths in Render
        base_dir = os.getcwd()
        global_path = os.path.join(base_dir, "config", "global_rules.yaml")
        project_path = os.path.join(base_dir, "config", "projects", f"{project_name}.yaml")
        
        if not os.path.exists(global_path):
            raise FileNotFoundError(f"CRITICAL: Global config missing at {global_path}")
        
        if not os.path.exists(project_path):
            raise FileNotFoundError(f"Project config missing: {project_name}")
        
        with open(global_path, "r", encoding="utf-8") as f:
            global_conf = yaml.safe_load(f) or {}
        
        with open(project_path, "r", encoding="utf-8") as f:
            project_conf = yaml.safe_load(f) or {}
        
        return ConfigLoader._deep_merge(global_conf, project_conf)
    
    @staticmethod
    def load_from_paths(global_path: str, project_path: str) -> Dict[str, Any]:
        """Load config from explicit paths (for local development)."""
        with open(global_path, "r", encoding="utf-8") as f:
            global_conf = yaml.safe_load(f) or {}
        
        with open(project_path, "r", encoding="utf-8") as f:
            project_conf = yaml.safe_load(f) or {}
        
        return ConfigLoader._deep_merge(global_conf, project_conf)
