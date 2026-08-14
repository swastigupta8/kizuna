from fastapi import FastAPI

app = FastAPI(title="Kizuna")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
