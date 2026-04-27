"""
Cliente DeepSeek (texto y visión) vía API HTTP.

Requiere el paquete ``requests`` en el entorno de ejecución
(p. ej. ``pip install requests`` o añadirlo a tus dependencias de despliegue).
"""

from __future__ import annotations

import os
from typing import Any, Mapping

try:
    import requests
except ImportError as exc:  # pragma: no cover - entorno sin requests
    raise ImportError(
        "Falta el paquete 'requests'. Instálalo en el entorno del servicio "
        "(por ejemplo: pip install requests)."
    ) from exc

_DEFAULT_BASE = "https://api.deepseek.com"
_TIMEOUT = 120


def _api_key() -> str:
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY no está definida")
    return key


def _base_url() -> str:
    return (os.environ.get("DEEPSEEK_API_BASE") or _DEFAULT_BASE).rstrip("/")


def _post_json(path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    url = f"{_base_url()}{path}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_api_key()}",
    }
    try:
        resp = requests.post(
            url,
            headers=headers,
            json=dict(payload),
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Error de red hacia DeepSeek: {exc}") from exc
    try:
        data = resp.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Respuesta no JSON de DeepSeek (HTTP {resp.status_code}): "
            f"{resp.text[:500]!r}",
        ) from exc
    if not resp.ok:
        raise RuntimeError(
            f"DeepSeek HTTP {resp.status_code}: {data if isinstance(data, dict) else resp.text!r}",
        )
    if not isinstance(data, dict):
        raise RuntimeError(f"Respuesta inesperada (no objeto JSON): {data!r}")
    return data


# --- Prompts internos para acciones de alto nivel (n8n / Hermes) ---


def build_analyze_text_prompt(text: str) -> str:
    """Instrucción para análisis detallado de un texto de usuario."""
    return (
        "Realiza un análisis detallado y bien estructurado del siguiente texto. "
        "Incluye: ideas principales, tono, intención del autor, matices y conclusiones "
        "útiles para quien lo lee.\n\n"
        f"Texto a analizar:\n{text.strip()}"
    )


def build_summarize_text_prompt(text: str) -> str:
    """Instrucción para resumir texto de usuario (conciso y claro)."""
    return f"Resume este texto de forma clara y concisa:\n\n{text.strip()}"


VISION_PROMPT_DESCRIBE = "Describe esta imagen con detalle."

VISION_PROMPT_OCR = "Extrae todo el texto legible de esta imagen."

VISION_PROMPT_ANALYZE = (
    "Analiza esta imagen: objetos, contexto, relaciones, riesgos, información relevante."
)


def _message_content(data: dict[str, Any]) -> str:
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Formato de respuesta inesperado: {data!r}") from exc
    if content is None:
        return ""
    if not isinstance(content, str):
        return str(content)
    return content


def deepseek_text(prompt: str) -> str:
    """
    Chat de texto con modelo ``deepseek-chat``.
    Devuelve únicamente el contenido del mensaje del asistente.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt debe ser un string no vacío")
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt.strip()}],
    }
    data = _post_json("/chat/completions", payload)
    return _message_content(data)


def deepseek_vision(image_url: str, prompt: str) -> str:
    """
    Visión con modelo ``deepseek-vl2``: ``prompt`` + ``image_url`` en el cuerpo
    (campo ``input_image`` en la raíz del JSON, más mensaje multimodal).
    Devuelve únicamente el contenido del mensaje del asistente.
    """
    if not isinstance(image_url, str) or not image_url.strip():
        raise ValueError("image_url debe ser un string no vacío")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt debe ser un string no vacío")
    url = image_url.strip()
    text = prompt.strip()
    payload = {
        "model": "deepseek-vl2",
        "input_image": url,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {"type": "input_image", "image_url": url},
                ],
            }
        ],
    }
    data = _post_json("/chat/completions", payload)
    return _message_content(data)
