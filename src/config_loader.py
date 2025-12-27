import yaml
import os
import copy
from typing import Dict, Any

class ConfigLoader:
    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Fusiona diccionarios recursivamente sin perder datos."""
        result = copy.deepcopy(base)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = ConfigLoader._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    @staticmethod
    def load(project_name: str) -> Dict[str, Any]:
        # Uso de os.getcwd() asegura rutas correctas en Render
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
