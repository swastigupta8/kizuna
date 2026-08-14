import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import db
from models import Finding
from parser import parse_compose_text
from score import compute_score

app = FastAPI(title="Kizuna")


class ScoreRequest(BaseModel):
    repo: str
    compose_yaml: str


class ScoreResponse(BaseModel):
    repo: str
    overall_score: float
    blast_radius_score: float
    recovery_score: float
    redundancy_score: float
    degradation_score: float
    findings: list[Finding]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/score", response_model=ScoreResponse)
def score_architecture(request: ScoreRequest) -> ScoreResponse:
    try:
        graph = parse_compose_text(request.compose_yaml)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"invalid YAML: {exc}") from exc

    if not graph.nodes:
        raise HTTPException(status_code=400, detail="no services found in compose file")

    result = compute_score(graph)
    db.save_score_run(request.repo, result)

    return ScoreResponse(
        repo=request.repo,
        overall_score=result.overall,
        blast_radius_score=result.blast_radius,
        recovery_score=result.recovery,
        redundancy_score=result.redundancy,
        degradation_score=result.degradation,
        findings=result.findings,
    )


@app.get("/api/v1/score/history/{repo:path}")
def score_history(repo: str, limit: int = 20) -> list[dict]:
    # ":path" lets `repo` contain slashes — repo ids look like "owner/repo"
    return db.get_score_history(repo, limit=limit)
