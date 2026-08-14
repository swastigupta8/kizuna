import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import db
from models import Finding
from parser import parse_compose_text
from remediate import generate_remediations
from score import compute_score

load_dotenv()

app = FastAPI(title="Kizuna")


class ScoreRequest(BaseModel):
    repo: str
    compose_yaml: str


class FindingWithRemediation(Finding):
    remediation: str | None = None


class ScoreResponse(BaseModel):
    repo: str
    overall_score: float
    blast_radius_score: float
    recovery_score: float
    redundancy_score: float
    degradation_score: float
    findings: list[FindingWithRemediation]


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

    remediations = generate_remediations(result.findings)
    findings_out = [
        FindingWithRemediation(**finding.model_dump(), remediation=remediations.get(i))
        for i, finding in enumerate(result.findings)
    ]

    return ScoreResponse(
        repo=request.repo,
        overall_score=result.overall,
        blast_radius_score=result.blast_radius,
        recovery_score=result.recovery,
        redundancy_score=result.redundancy,
        degradation_score=result.degradation,
        findings=findings_out,
    )


@app.get("/api/v1/score/history/{repo:path}")
def score_history(repo: str, limit: int = 20) -> list[dict]:
    # ":path" lets `repo` contain slashes — repo ids look like "owner/repo"
    return db.get_score_history(repo, limit=limit)
