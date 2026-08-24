import json
from pathlib import Path

source_path = Path("scenarios/debate/cve_seeds_500.jsonl")
out_jsonl = Path("scenarios/debate/cve_sample_10.jsonl")
out_eval_json = Path("tests/eval/datasets/cve_sample_10_eval.json")

samples = []
with open(source_path, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        if idx >= 10:
            break
        line_str = line.strip()
        if line_str:
            samples.append(json.loads(line_str))

# Write JSONL
with open(out_jsonl, "w", encoding="utf-8") as f:
    for s in samples:
        f.write(json.dumps(s) + "\n")

print(f"Wrote {len(samples)} samples to {out_jsonl}")

# Write ADK Eval Dataset JSON
eval_cases = []
for idx, s in enumerate(samples, 1):
    predicate = s.get("predicate", "")
    code = s.get("topic", "")
    eval_cases.append({
        "eval_case_id": f"cve_seed_{idx:02d}",
        "prompt": {
            "role": "user",
            "parts": [
                {
                    "text": (
                        f"Run a security debate audit on the following code for the predicate: \"{predicate}\"\n\n"
                        f"```c\n{code}\n```"
                    )
                }
            ]
        }
    })

eval_dataset = {"eval_cases": eval_cases}
out_eval_json.parent.mkdir(parents=True, exist_ok=True)
with open(out_eval_json, "w", encoding="utf-8") as f:
    json.dump(eval_dataset, f, indent=2)

print(f"Wrote {len(eval_cases)} eval cases to {out_eval_json}")
