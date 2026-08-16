# Kizuna

I kept running into the same idea while reading about SRE postmortems: teams almost always say "we should have caught this at design time," but there's no widely-used tool that actually does that for reliability — the way `terraform plan`, security scanners, and test coverage gates already do for their own domains. So I built one.

**Kizuna reads a `docker-compose.yml`, scores the architecture for resilience, explains what's wrong in plain English, and can automatically fail a GitHub pull request before a fragile change ever merges.**

**Live app:** [kizuna-2iar.onrender.com](https://kizuna-2iar.onrender.com) · **A real PR the gate actually caught:** [kizuna-demo #1](https://github.com/swastigupta8/kizuna-demo/pull/1)

(Quick naming note: this project was called "Chronos" early on. Kizuna — 絆, Japanese for "bond" or "tie" — felt more honest once the scope settled, since the whole thing is really just about the ties between services and what happens when one breaks.)

## What it actually does

1. **Parses** your `docker-compose.yml` into a dependency graph — which service talks to which, and any resilience config (circuit breakers, timeouts, replica counts) you've declared via labels.
2. **Scores it four separate ways**, each one a real calculation, not an LLM guessing:
   - **Redundancy** — Tarjan's articulation-point algorithm, finding genuine single points of failure in the graph's structure.
   - **Blast radius** — an in-memory simulation that propagates a failure outward and measures how much of the system goes down with it.
   - **Recovery** — how long that simulated cascade takes to settle, measured against a configurable SLA target.
   - **Degradation** — a rule-based linter, the same shape as ESLint, checking for missing timeouts, naive retries, and single-replica critical services.
3. **Explains the findings in plain English**, using an LLM — but only for this layer. The score itself stays fully deterministic, because a CI gate that gives different answers for the same input isn't a gate anyone can trust.
4. **Gates a real GitHub PR** — a workflow calls the score, posts it as a comment, and fails the check if the architecture dropped below a threshold.

## See it in action

Same scoring engine, four different architectures, spanning the full range from "genuinely solid" to "one outage away from a bad night."

*(add screenshot of the excellent-tier dashboard here — 86/100)*

*(add screenshot of the healthy-tier dashboard here — 82.5/100)*

*(add screenshot of the needs-attention dashboard here — 71/100)*

*(add screenshot of the at-risk dashboard here — 49.8/100)*

Every one of those is a real compose file run through the real engine — see [`demo-repo/scenarios/`](demo-repo/scenarios/) if you want to check my work.

**The part I'd actually point you to first:** [kizuna-demo #1](https://github.com/swastigupta8/kizuna-demo/pull/1) — a real pull request that adds an unprotected service dependency. The gate genuinely fails it, with an LLM-written fix suggestion in the comment, and then genuinely passes once the fix goes in. That loop — break it, catch it, fix it, watch it go green — is the entire pitch in one link.

## Try it yourself

No signup, no CLI, no account needed anywhere. Go to **[kizuna-2iar.onrender.com](https://kizuna-2iar.onrender.com)**, drop in a `docker-compose.yml`, give it a project name, and you'll land on a dashboard within a few seconds.

*(add screenshot of the upload page here)*

One thing worth knowing before you try your own file: a plain compose file with no labels will score low, and that's not a bug — Kizuna can't see a circuit breaker in your actual code, only in labels you add telling it one exists (`kizuna.circuit_breaker=true`, `kizuna.timeout_ms=2000`, etc.). The upload page has a "What should be in the file?" section with the exact format if you want to see your real setup reflected accurately.

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

That's genuinely close to the whole thing — the full working example, including the check script, is in [`demo-repo/.github/`](https://github.com/swastigupta8/kizuna-demo/tree/main/.github).

## Stack

Python · FastAPI · Pydantic · Turso (libSQL) · Jinja2 · Gemini API (forced function-calling, not free-text parsing) · GitHub Actions · deployed on Render's free tier.

No Kubernetes, no Kafka, no React — not because they're bad tools, but because none of them were actually needed here, and reaching for them anyway would have meant a lot of infrastructure theater standing between me and the part of this project that's actually interesting: the scoring engine itself.

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

Then visit `http://127.0.0.1:8000`. Run the tests with `.venv\Scripts\python -m pytest` — 47 of them, all mocking the LLM boundary, so none need a real API key to pass.

## A few design decisions worth knowing about

- **The score is deterministic; the LLM is isolated on purpose.** `score.py` never imports `remediate.py`, and every failure mode in the LLM call — missing key, network error, a bad response — returns an empty mapping instead of raising. A missing explanation should never be able to take the gate down with it.
- **Blast radius mathematically can't reach a perfect 100** for any graph with a critical node in it, since a failing node always counts as affecting at least itself. Worth knowing that going in rather than being confused by it later.
- **Redundancy and blast radius catch genuinely different failure modes.** A database that three services all depend on independently can be structurally redundant — multiple paths through the graph — while still being a real operational risk if it goes down. The "excellent" scenario above shows exactly this: 100/100 redundancy, and still one honest blast-radius finding.

## Known limitations

Being upfront about what's not solved here yet:

- No auth or multi-tenancy — this is a single shared instance, which is fine for a demo and not something I'd ship for real multi-team use as-is.
- No rate limiting on the scoring endpoint yet.
- The resilience-factor constants (a circuit breaker absorbs 60% of propagated severity, a bare retry absorbs 20%) were chosen because they're plausible, not because they're empirically calibrated against real systems.

## License

MIT
