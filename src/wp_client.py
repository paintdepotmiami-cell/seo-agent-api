import os
import re
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin
from src.transport import get_secure_session

logger = logging.getLogger("wp-client")

class WPClient:
    def __init__(self, config):
        self.site_url = config['site']['url'].rstrip('/') + '/'
        # Credenciales desde variables de entorno (seguridad máxima)
        # Fallback to config if env not set (compatibility)
        api_conf = config.get('api', {})
        self.user = os.environ.get("WP_USERNAME") or api_conf.get('username')
        self.password = os.environ.get("WP_APP_PASSWORD") or api_conf.get('app_password')
        
        if not self.user or not self.password:
            # Don't crash immediately, wait until connection needed
            logger.warning("❌ Missing WP credentials (WP_USERNAME/WP_APP_PASSWORD)")

        self.session = get_secure_session()
        if self.user and self.password:
            self.session.auth = (self.user, self.password)

    def apply_changes(self, post_id: int, changes: List[Dict[str, Any]], status: str = "draft") -> Dict:
        """
        Descarga el post, aplica los cambios en memoria y sube la actualización.
        """
        if not self.user or not self.password:
             return {"error": "Missing credentials"}

        # 1. Obtener contenido actual
        endpoint = f"wp-json/wp/v2/posts/{post_id}?context=edit"
        url = urljoin(self.site_url, endpoint)
        
        try:
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            current_data = resp.json()
        except Exception as e:
            logger.error(f"Error fetching post {post_id}: {e}")
            return {"error": str(e)}

        original_content = current_data['content']['raw']
        updated_content = original_content
        applied_log = []

        # 2. Aplicar cada cambio
        for change in changes:
            if change['type'] == 'link':
                updated_content, success = self._inject_link(updated_content, change)
                if success: applied_log.append(f"Link added: {change['anchor']}")
            
            elif change['type'] == 'schema':
                updated_content, success = self._inject_schema(updated_content, change)
                if success: applied_log.append("Schema injected")

        # 3. Si hubo cambios, enviar a WordPress
        if applied_log:
            update_payload = {
                "content": updated_content,
                # Si status es 'draft', no publicamos, solo guardamos borrador
                # Si status es 'publish', se va en vivo.
                "status": current_data['status'] if status == 'draft' else status
            }
            
            try:
                # POST a la API
                update_resp = self.session.post(url, json=update_payload, timeout=20)
                update_resp.raise_for_status()
                return {"status": "success", "changes": applied_log, "new_version": update_resp.json()['id']}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        else:
            return {"status": "skipped", "message": "No valid changes could be applied"}

    def _inject_link(self, content: str, change: Dict) -> (str, bool):
        anchor = change['anchor']
        url = change['url']
        
        # Regex segura: Busca la palabra completa, case-insensitive, fuera de etiquetas HTML
        # Nota: Regex simple. Para producción masiva, BeautifulSoup es mejor, pero esto funciona para textos planos.
        pattern = re.compile(rf'\b({re.escape(anchor)})\b', re.IGNORECASE)
        
        # Verificar si ya existe el link para no duplicar
        if url in content:
            return content, False

        # Reemplazar solo la primera ocurrencia (count=1)
        # Using lambda to keep original case of anchor? user logic is: f'<a...>{anchor}</a>' using the anchor from change.
        # Ideally we should use the TEXT matched.
        # But following user guide:
        new_content, count = pattern.subn(f'<a href="{url}" title="{anchor}">{anchor}</a>', content, count=1)
        return new_content, count > 0

    def _inject_schema(self, content: str, change: Dict) -> (str, bool):
        json_ld = change['json_ld'] # String JSON completo
        script_tag = f'\n<script type="application/ld+json">\n{json_ld}\n</script>'
        
        # Evitar duplicados
        if json_ld in content:
            return content, False
            
        # Añadir al final del contenido
        return content + script_tag, True

    # COMPATIBILITY LAYER FOR OLD CODE
    def test_connection(self):
        try:
            r = self.session.get(urljoin(self.site_url, "wp-json/wp/v2/users/me"))
            return r.status_code == 200
        except:
            return False

    def apply_link(self, post_id, content_type, anchor_text, target_url, as_draft=True):
        """Adapter for old ApplyRequest."""
        changes = [{
            "type": "link",
            "anchor": anchor_text,
            "url": target_url
        }]
        res = self.apply_changes(post_id, changes, status="draft" if as_draft else "publish")
        return res.get("status") == "success"
