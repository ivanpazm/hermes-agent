"""
API FastAPI para n8n + acciones DeepSeek (Hermes Agent / servicio ligero).
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from app.deepseek import (
    VISION_PROMPT_ANALYZE,
    VISION_PROMPT_DESCRIBE,
    VISION_PROMPT_OCR,
    build_analyze_text_prompt,
    build_summarize_text_prompt,
    deepseek_text,
    deepseek_vision,
)

app = FastAPI(title="Hermes Agent — n8n bridge")

N8N_API_KEY = (os.environ.get("N8N_API_KEY") or "").strip()
DEEPSEEK_API_KEY_PRESENT = bool((os.environ.get("DEEPSEEK_API_KEY") or "").strip())


def _require_n8n_config() -> None:
    if not N8N_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="N8N_API_KEY no está configurada",
        )


def _authorize(request: Request) -> None:
    _require_n8n_config()
    auth = request.headers.get("authorization")
    expected = f"Bearer {N8N_API_KEY}"
    if auth != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _invoke_deepseek_text(prompt: str) -> str:
    if not DEEPSEEK_API_KEY_PRESENT:
        raise HTTPException(
            status_code=503,
            detail="DEEPSEEK_API_KEY no está configurada",
        )
    try:
        return deepseek_text(prompt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _invoke_deepseek_vision(image_url: str, prompt: str) -> str:
    if not DEEPSEEK_API_KEY_PRESENT:
        raise HTTPException(
            status_code=503,
            detail="DEEPSEEK_API_KEY no está configurada",
        )
    try:
        return deepseek_vision(image_url, prompt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "Hermes Agent running"}


@app.post("/api/n8n/action")
async def n8n_action(request: Request) -> dict[str, Any]:
    _authorize(request)

    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001 — JSON inválido
        raise HTTPException(status_code=400, detail="Cuerpo JSON inválido") from exc

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="El cuerpo debe ser un objeto JSON")

    action = body.get("action")
    data = body.get("data")

    if data is not None and not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="data debe ser un objeto o omitirse")

    payload: dict[str, Any] = data if isinstance(data, dict) else {}

    if action == "echo":
        return {"status": "ok", "data": payload}

    if action == "deepseek_text":
        prompt = payload.get("prompt")
        if not isinstance(prompt, str):
            raise HTTPException(status_code=400, detail="data.prompt debe ser un string")
        result = _invoke_deepseek_text(prompt)
        return {"status": "ok", "result": result}

    if action == "deepseek_vision":
        image_url = payload.get("image_url")
        prompt = payload.get("prompt")
        if not isinstance(image_url, str):
            raise HTTPException(
                status_code=400,
                detail="data.image_url debe ser un string",
            )
        if not isinstance(prompt, str):
            raise HTTPException(
                status_code=400,
                detail="data.prompt debe ser un string",
            )
        vision = _invoke_deepseek_vision(image_url, prompt)
        return {"status": "ok", "vision": vision}

    if action == "analyze_text":
        text = payload.get("text")
        if not isinstance(text, str):
            raise HTTPException(status_code=400, detail="data.text debe ser un string")
        analysis = _invoke_deepseek_text(build_analyze_text_prompt(text))
        return {"status": "ok", "analysis": analysis}

    if action == "summarize_text":
        text = payload.get("text")
        if not isinstance(text, str):
            raise HTTPException(status_code=400, detail="data.text debe ser un string")
        summary = _invoke_deepseek_text(build_summarize_text_prompt(text))
        return {"status": "ok", "summary": summary}

    if action == "vision_describe":
        image_url = payload.get("image_url")
        if not isinstance(image_url, str):
            raise HTTPException(
                status_code=400,
                detail="data.image_url debe ser un string",
            )
        description = _invoke_deepseek_vision(image_url, VISION_PROMPT_DESCRIBE)
        return {"status": "ok", "description": description}

    if action == "vision_ocr":
        image_url = payload.get("image_url")
        if not isinstance(image_url, str):
            raise HTTPException(
                status_code=400,
                detail="data.image_url debe ser un string",
            )
        ocr = _invoke_deepseek_vision(image_url, VISION_PROMPT_OCR)
        return {"status": "ok", "ocr": ocr}

    if action == "vision_analyze":
        image_url = payload.get("image_url")
        if not isinstance(image_url, str):
            raise HTTPException(
                status_code=400,
                detail="data.image_url debe ser un string",
            )
        analysis = _invoke_deepseek_vision(image_url, VISION_PROMPT_ANALYZE)
        return {"status": "ok", "analysis": analysis}

    name = action if isinstance(action, str) else repr(action)
    return {"status": "error", "message": f"Unknown action: {name}"}
