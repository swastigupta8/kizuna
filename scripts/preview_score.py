"""Dev tool: preview the score a compose file would get, without hitting the API or DB."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parser import parse_compose  # noqa: E402
from score import compute_score  # noqa: E402

compose_path = sys.argv[1]
graph = parse_compose(compose_path)
result = compute_score(graph)

print(f"overall: {result.overall}")
print(f"  blast_radius: {result.blast_radius}")
print(f"  recovery:     {result.recovery}")
print(f"  redundancy:   {result.redundancy}")
print(f"  degradation:  {result.degradation}")
print(f"\nfindings ({len(result.findings)}):")
for f in result.findings:
    print(f"  [{f.severity.value}] {f.node_id}: {f.message}")
