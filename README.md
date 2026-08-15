# Kizuna

**A shift-left resilience gate for microservice architectures.** Kizuna reads a `docker-compose.yml`, scores the architecture for resilience using graph theory and a real cascade simulation, explains what's wrong in plain English via an LLM, and can automatically fail a GitHub pull request before a fragile change ever merges.

**Live app:** [kizuna-2iar.onrender.com](https://kizuna-2iar.onrender.com) · **Demo repo with a real merged PR:** [kizuna-demo #1](https://github.com/swastigupta8/kizuna-demo/pull/1)

Kizuna is a rename of an earlier working title, "Chronos" — 絆 (*kizuna*) is Japanese for "bond" or "tie," which is what the dependency edges in the architecture graph actually are.

## Why

Security tooling shifted left a decade ago — `terraform plan`, SAST scanners, and test coverage gates all catch problems before merge, not after deploy. Reliability never got the same treatment: most resilience testing still happens against systems that are already live. Kizuna asks a narrower question at the right time: **if this PR merges, does the system get measurably more fragile?**

## What it actually does

1. **Parses** your `docker-compose.yml` into a dependency graph — services, what talks to what, and any resilience config (circuit breakers, timeouts, replica counts) declared via labels.
2. **Scores it four ways**, each independently real, not just LLM vibes:
   - **Redundancy** — Tarjan's articulation-point algorithm finds genuine single points of failure in the graph structure.
   - **Blast radius** — an in-memory cascade simulation propagates a failure outward and measures how much of the system goes down with it.
   - **Recovery** — derived from how long that simulated cascade takes to stabilize against a configurable SLA target.
   - **Degradation** — a rule-based linter (the same shape as ESLint) checking for missing timeouts, naive retries, and single-replica critical services.
3. **Explains the findings** using an LLM (Gemini), which only ever touches this human-readable layer — the score itself is deterministic, because a CI gate has to give the same architecture the same result every time.
4. **Gates a GitHub PR** — a workflow calls the score, posts it as a PR comment, and fails the check below a threshold.

## See it in action

| Excellent (86/100) | Healthy (82.5/100) |
|---|---|
| ![Excellent architecture](docs/screenshots/dashboard-excellent.png) | ![Healthy architecture](docs/screenshots/dashboard-healthy.png) |

| Needs attention (71/100) | At risk (49.8/100) |
|---|---|
| ![Needs attention](docs/screenshots/dashboard-needs-attention.png) | ![At risk architecture](docs/screenshots/dashboard-at-risk.png) |

The same architecture, scored across the full range — from a well-protected system with genuine redundancy down to a linear chain with no safety nets at all. Every score above comes from a real compose file run through the real scoring engine (see [`demo-repo/scenarios/`](demo-repo/scenarios/)), not staged data.

**The actual CI gate, on a real PR:** [kizuna-demo #1](https://github.com/swastigupta8/kizuna-demo/pull/1) — a PR that adds an unprotected service dependency, watch the gate genuinely fail with an LLM-written fix suggestion, then pass after the fix.

## Try it yourself

No signup, no CLI. Go to **[kizuna-2iar.onrender.com](https://kizuna-2iar.onrender.com)**, drop in any `docker-compose.yml`, give it a project name, and you'll land on a dashboard with your score, findings, and suggested fixes within a few seconds.

![Upload page](docs/screenshots/upload-page.png)

## Wiring it into your own CI

```yaml
# .github/workflows/kizuna.yml
name: Kizuna Resilience Check
on:
  pull_request:
    paths: ["docker-compose.yml"]
permissions:
  pull-requests: write
jobs:
  resilience-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 .github/scripts/kizuna_check.py
        env:
          KIZUNA_API_URL: ${{ secrets.KIZUNA_API_URL }}
          SCORE_THRESHOLD: "80"
      - if: always()
        uses: marocchino/sticky-pull-request-comment@v2
        with:
          path: kizuna_comment.md
```

Full working example, including the check script: [`demo-repo/.github/`](https://github.com/swastigupta8/kizuna-demo/tree/main/.github).

## Stack

Python 3.14 · FastAPI · Pydantic · SQLite · Jinja2 · Gemini API (`google-genai`, forced function-calling) · GitHub Actions · deployed on Render's free tier.

Deliberately not Kubernetes, Kafka, or React — see [architecture notes](#design-notes) below for why.

## Running it locally

```bash
git clone https://github.com/swastigupta8/kizuna
cd kizuna
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt      # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux

cp .env.example .env   # add your own GEMINI_API_KEY
.venv\Scripts\python -m uvicorn main:app --reload
```

Then visit `http://127.0.0.1:8000`. Run the test suite with `.venv\Scripts\python -m pytest` — 47 tests, all mocking the LLM boundary so none require a real API key.

## Design notes

- **The score is deterministic; the LLM is isolated.** `score.py` never imports `remediate.py`. Every failure mode in the LLM call (missing key, network error, bad response) returns an empty mapping rather than raising — a missing explanation should never be able to break the gate.
- **Blast radius mathematically can't reach 100** for any graph with a critical node, since the failing node always counts as affecting itself. Worth knowing going in, not discovering by surprise.
- **Redundancy and blast radius catch different things.** A shared database that three services all depend on independently can be structurally redundant (multiple paths through the graph) while still being an operational risk if it fails — that's exactly what the "excellent" scenario above shows: 100/100 redundancy, and still one real blast-radius finding.

## Known limitations

- No auth or multi-tenancy — this is a single shared instance, fine for a demo, not for production multi-team use.
- Render's free tier has ephemeral disk, so score history can reset on redeploy. *(Being migrated to persistent storage — see open issues.)*
- The resilience-factor constants (circuit breaker absorbs 60% of propagated severity, retry absorbs 20%) are chosen for a plausible demo, not empirically calibrated.
- No rate limiting on the scoring endpoint yet.

## License

MIT
