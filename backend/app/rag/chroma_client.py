"""Cliente de Chroma en modo servidor (E00 · T00.3.1 · actualizado en E01 · Paso 0).

Expone `get_chroma_client()`, que devuelve un `HttpClient` apuntando al servidor
Chroma que corre en el contenedor `aquamarine-chroma` (`settings.CHROMA_HOST`:
`settings.CHROMA_PORT`) y garantiza que exista la colección `inmuebles`
(get-or-create). Devuelve el **cliente**, no la colección.
"""

import chromadb
from chromadb.api import ClientAPI

from app.core.config import settings

COLLECTION_NAME = "inmuebles"


def get_chroma_client() -> ClientAPI:
    """Retorna un HttpClient de Chroma con la colección 'inmuebles' lista."""
    client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
    # get-or-create: idempotente, no falla si la colección ya existe.
    client.get_or_create_collection(name=COLLECTION_NAME)
    return client
