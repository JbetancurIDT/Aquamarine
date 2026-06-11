"""Valores válidos del dominio (E02 · Backend Core).

Se usan como tipos en los schemas Pydantic (Pydantic valida la pertenencia y
devuelve 422 si llega un valor inválido) y para validar en el servicio.
"""

from enum import Enum


class Origen(str, Enum):
    """Canal de origen del lead."""

    web = "web"
    meta = "meta"
    metrocuadrado = "metrocuadrado"
    fincaraiz = "fincaraiz"


class Temperatura(str, Enum):
    """Temperatura del lead (qué tan caliente es la oportunidad)."""

    caliente = "caliente"
    tibio = "tibio"
    frio = "frio"
    desconocido = "desconocido"  # handoff por solicitud antes de calificar (D15)


class Estado(str, Enum):
    """Estado del lead en el pipeline (embudo)."""

    nuevo = "nuevo"
    contactado = "contactado"
    calificado = "calificado"
    negociando = "negociando"
    cerrado_ganado = "cerrado_ganado"
    cerrado_perdido = "cerrado_perdido"
    descartado = "descartado"


class Rol(str, Enum):
    """Rol del autor de un mensaje en la conversación."""

    lead = "lead"
    agente = "agente"
    asesor = "asesor"
