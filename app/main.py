from fastapi import FastAPI, Request, HTTPException
import os

app = FastAPI()

API_KEY = os.getenv("N8N_API_KEY")


@app.get("/")
def root():
    return {"status": "Hermes Agent running"}


@app.post("/api/n8n/action")
async def n8n_action(request: Request):
    auth = request.headers.get("authorization")
    if auth != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    action = body.get("action")
    data = body.get("data")

    return {
        "status": "ok",
        "received_action": action,
        "received_data": data,
    }
