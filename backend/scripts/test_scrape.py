"""Guardrail de verificación de T01.1.1 (cliente Firecrawl + scrape_url).

Dos modos:
- Caso A (offline, SIEMPRE corre, sin key ni red): mockea el SDK de Firecrawl y
  verifica que (i) scrape_url devuelve el dict esperado con markdown y (ii) sin
  FIRECRAWL_API_KEY se lanza un ValueError claro. Prueba la lógica sin gastar API.
- Caso B (smoke real, opcional): si hay FIRECRAWL_API_KEY y se pasa una URL como
  argumento, hace un scrape real e imprime los primeros 500 chars del markdown.

Uso:
    .venv/bin/python scripts/test_scrape.py            # solo Caso A (offline)
    .venv/bin/python scripts/test_scrape.py <URL>      # Caso A + Caso B (real)
"""

import sys
from pathlib import Path

# Permite ejecutar el script directamente: inserta la raíz de backend/ en sys.path
# (el padre de scripts/) para que `import app...` funcione sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag import firecrawl_client  # noqa: E402


class _FakeDocument:
    """Imita el Document del SDK de Firecrawl: solo necesita el atributo .markdown."""

    def __init__(self, markdown: str):
        self.markdown = markdown


class _FakeFirecrawl:
    """Imita firecrawl.Firecrawl: guarda la api_key y devuelve un doc fijo en scrape()."""

    MARKDOWN = "# Casa en El Poblado\n\n3 habitaciones, 2 baños, 180 m2. Vista a la ciudad."

    def __init__(self, api_key=None, **kwargs):
        self.api_key = api_key
        self.llamadas = []

    def scrape(self, url, **kwargs):
        self.llamadas.append((url, kwargs))
        return _FakeDocument(self.MARKDOWN)


def caso_a_offline() -> None:
    """Caso A: lógica de scrape_url con el SDK mockeado + ValueError sin key."""
    # Guardamos los originales para restaurarlos (no contaminar el Caso B ni el proceso).
    sdk_real = firecrawl_client.Firecrawl
    key_real = firecrawl_client.settings.FIRECRAWL_API_KEY
    try:
        # (i) Con key + SDK mockeado: scrape_url devuelve el dict esperado con markdown.
        firecrawl_client.Firecrawl = _FakeFirecrawl
        firecrawl_client.settings.FIRECRAWL_API_KEY = "fc-test-offline"
        url = "https://ejemplo-inmobiliaria.test/inmueble/123"
        resultado = firecrawl_client.scrape_url(url)
        assert resultado == {"url": url, "markdown": _FakeFirecrawl.MARKDOWN}, resultado
        assert resultado["markdown"], "el markdown no debería venir vacío"
        print("[Caso A.i] scrape_url devuelve dict con markdown -> OK")

        # (ii) Sin key: se lanza un ValueError claro (no un traceback del SDK).
        firecrawl_client.settings.FIRECRAWL_API_KEY = ""
        try:
            firecrawl_client.scrape_url(url)
        except ValueError as exc:
            assert "FIRECRAWL_API_KEY" in str(exc), str(exc)
            print(f"[Caso A.ii] sin key lanza ValueError claro -> OK ({exc})")
        else:
            raise AssertionError("Se esperaba ValueError cuando falta FIRECRAWL_API_KEY")
    finally:
        firecrawl_client.Firecrawl = sdk_real
        firecrawl_client.settings.FIRECRAWL_API_KEY = key_real

    print("[Caso A] OFFLINE OK ✅")


def caso_b_real(url: str) -> None:
    """Caso B (opcional): scrape real contra la URL pasada como argumento."""
    if not (firecrawl_client.settings.FIRECRAWL_API_KEY or "").strip():
        print("[Caso B] omitido: no hay FIRECRAWL_API_KEY en backend/.env")
        return
    print(f"[Caso B] scrape real de: {url}")
    resultado = firecrawl_client.scrape_url(url)
    markdown = resultado.get("markdown", "")
    print("---- primeros 500 chars del markdown ----")
    print(markdown[:500])
    print("---- fin ----")
    print(f"[Caso B] OK ✅ (markdown de {len(markdown)} chars)")


def main() -> int:
    # Caso A siempre corre: offline, sin red ni key.
    caso_a_offline()

    # Caso B solo si se pasa una URL como argumento.
    if len(sys.argv) > 1:
        caso_b_real(sys.argv[1])
    else:
        print("[Caso B] omitido: no se pasó URL como argumento (modo offline).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
