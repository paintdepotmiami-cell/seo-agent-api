import requests

def get_secure_session():
    """
    Devuelve una sesión de Requests lista para SiteGround.
    NOTA: Se ha simplificado para usar la configuración estándar que demostró 
    funcionar (Golden Master), ya que el TLSAdapter agresivo causaba bloqueos WAF.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "SEOIntelligenceAgent/1.0 (Compatible; +http://localhost)",
        "Accept": "application/json"
    })
    return session
