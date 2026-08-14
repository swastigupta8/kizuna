import json
import pathlib
import sys

compose_path = pathlib.Path(sys.argv[1])
repo = sys.argv[2]
out_path = pathlib.Path(sys.argv[3])

payload = {"repo": repo, "compose_yaml": compose_path.read_text()}
out_path.write_text(json.dumps(payload))
