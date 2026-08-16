import json
from datetime import datetime, timedelta, timezone

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import db
from models import Finding
from parser import parse_compose_text
from remediate import generate_remediations
from score import compute_score

load_dotenv()

app = FastAPI(title="Kizuna")
templates = Jinja2Templates(directory="templates")

IST = timezone(timedelta(hours=5, minutes=30))
_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}


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


def _to_ist(iso_timestamp: str, *, short: bool = False) -> str:
    dt = datetime.fromisoformat(iso_timestamp).astimezone(IST)
    return dt.strftime("%d %b, %I:%M %p") if short else dt.strftime("%d %b %Y, %I:%M %p IST")


def _worst_severity_per_node(findings: list[dict]) -> dict[str, str]:
    worst: dict[str, str] = {}
    for finding in findings:
        node_id, severity = finding["node_id"], finding["severity"]
        if node_id not in worst or _SEVERITY_RANK[severity] > _SEVERITY_RANK[worst[node_id]]:
            worst[node_id] = severity
    return worst


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root(request: Request):
    return templates.TemplateResponse(request=request, name="upload.html", context={})


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

    remediations = generate_remediations(result.findings)
    findings_out = [
        FindingWithRemediation(**finding.model_dump(), remediation=remediations.get(i))
        for i, finding in enumerate(result.findings)
    ]

    db.save_score_run(
        request.repo,
        result.overall,
        result.blast_radius,
        result.recovery,
        result.redundancy,
        result.degradation,
        [finding.model_dump() for finding in findings_out],
        graph.model_dump(),
    )

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


@app.get("/dashboard/{repo:path}", response_class=HTMLResponse)
def dashboard(request: Request, repo: str):
    history = db.get_score_history(repo, limit=50)

    # No history yet (or free-tier disk got wiped on redeploy) still renders a
    # real page — a route a human visits in a browser should never come back
    # as a bare 404, even when the underlying condition genuinely is "empty."
    if not history:
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={"repo": repo, "latest": None, "history_labels": [], "history_scores": []},
        )

    latest = dict(history[0])
    latest["findings"] = json.loads(latest["findings_json"])
    latest["created_at"] = _to_ist(latest["created_at"])

    graph = json.loads(latest["graph_json"]) if latest.get("graph_json") else None
    node_severity = _worst_severity_per_node(latest["findings"]) if graph else {}

    chronological = list(reversed(history))  # oldest -> newest, for the chart

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "repo": repo,
            "latest": latest,
            "graph": graph,
            "node_severity": node_severity,
            "history_labels": [_to_ist(row["created_at"], short=True) for row in chronological],
            "history_scores": [row["overall_score"] for row in chronological],
        },
    )
