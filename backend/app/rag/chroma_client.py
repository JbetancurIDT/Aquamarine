"""Cliente de Chroma persistente (E00 · T00.3.1).

Expone `get_chroma_client()`, que devuelve un `PersistentClient` apuntando a
`settings.CHROMA_PERSIST_DIR` y garantiza que exista la colección `inmuebles`
(get-or-create). Devuelve el **cliente**, no la colección.
"""

import chromadb
from chromadb.api import ClientAPI

from app.core.config import settings

COLLECTION_NAME = "inmuebles"


def get_chroma_client() -> ClientAPI:
    """Retorna un PersistentClient de Chroma con la colección 'inmuebles' lista."""
    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    # get-or-create: idempotente, no falla si la colección ya existe.
    client.get_or_create_collection(name=COLLECTION_NAME)
    return client
