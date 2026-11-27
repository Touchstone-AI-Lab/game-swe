#!/usr/bin/env bash
set -euo pipefail

task=${1:?usage: validate-task.sh <task-id> [oracle|ablation]}
control=${2:-oracle}
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
harbor_root=$(cd "$script_dir/.." && pwd -P)
repository_root=$(cd "$harbor_root/../../../.." && pwd -P)
results_dir=${RHENIUM_MINDUSTRY_VALIDATION_DIR:-$repository_root/.rhenium/harbor-jobs}

[[ -f "$harbor_root/$task/task.toml" ]] || {
  printf 'unknown Mindustry Harbor task: %s\n' "$task" >&2
  exit 2
}

case $control in
  oracle)
    agent=oracle
    expected_reward=1.0
    dataset_root=$harbor_root
    ;;
  ablation)
    agent=oracle
    expected_reward=0.0
    manifest=$harbor_root/$task/validation/ablations/manifest.tsv
    [[ -f $manifest ]] || {
      printf 'missing ablation manifest: %s\n' "$manifest" >&2
      exit 2
    }
    ;;
  *)
    printf 'control must be oracle or ablation: %s\n' "$control" >&2
    exit 2
    ;;
esac

harbor_bin=${HARBOR_BIN:-}
if [[ -z $harbor_bin ]]; then
  harbor_bin=$(command -v harbor || true)
fi
if [[ -z $harbor_bin && -x ${HOME:-}/.local/bin/harbor ]]; then
  harbor_bin=${HOME}/.local/bin/harbor
fi
[[ -n $harbor_bin && -x $harbor_bin ]] || {
  printf 'Harbor CLI is required; install harbor==0.23.0 with uv tool install\n' >&2
  exit 2
}

mkdir -p "$results_dir"
run_results="$results_dir/$(date +%Y%m%d-%H%M%S)-$task-$control-$$"
mkdir -p "$run_results"
if [[ $control == ablation ]]; then
  IFS=$'\t' read -r ablation patch_file expected_failed_case < <(tail -n +2 "$manifest")
  [[ -n $ablation && -n $patch_file && -n $expected_failed_case ]] || {
    printf 'invalid ablation manifest: %s\n' "$manifest" >&2
    exit 2
  }
  dataset_root=$run_results/dataset
  mkdir -p "$dataset_root"
  cp -R "$harbor_root/$task" "$dataset_root/$task"
  patch -s -d "$dataset_root/$task" -p1 \
    < "$harbor_root/$task/validation/ablations/$patch_file"
fi
"$harbor_bin" run \
  --path "$dataset_root" \
  --include-task-name "$task" \
  --agent "$agent" \
  --jobs-dir "$run_results" \
  --n-concurrent 1

job_result=$(find "$run_results" -mindepth 2 -maxdepth 2 -name result.json -type f -print -quit)
[[ -n $job_result ]] || {
  printf 'Harbor did not write a job result for %s\n' "$task" >&2
  exit 1
}

verifier_log=$(find "$run_results" -mindepth 4 -maxdepth 4 -path '*/verifier/verifier.log' -type f -print -quit)

python3 - "$job_result" "$verifier_log" "$task" "$control" "$expected_reward" "${expected_failed_case:-}" <<'PY'
import json
import sys
from pathlib import Path

result_path = Path(sys.argv[1])
log_path = Path(sys.argv[2]) if sys.argv[2] else None
task = sys.argv[3]
control = sys.argv[4]
expected_reward = float(sys.argv[5])
expected_failed_case = sys.argv[6]
result = json.loads(result_path.read_text(encoding="utf-8"))
stats = result.get("stats", {})
evals = stats.get("evals", {})
metrics = [
    metric
    for evaluation in evals.values()
    for metric in evaluation.get("metrics", [])
]
passed = (
    result.get("n_total_trials") == 1
    and stats.get("n_completed_trials") == 1
    and stats.get("n_errored_trials") == 0
    and len(metrics) == 1
    and metrics[0].get("mean") == expected_reward
)
if not passed:
    raise SystemExit(
        f"Mindustry Harbor {control} control did not match reward "
        f"{expected_reward}: {task}"
    )
if control == "ablation":
    if log_path is None or not log_path.is_file():
        raise SystemExit(f"missing verifier log for ablation: {task}")
    text = log_path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    reports = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("cases"), list):
            reports.append(value)
    if not reports:
        raise SystemExit(f"missing case report for ablation: {task}")
    cases = reports[-1]["cases"]
    outcomes = {case.get("name"): case.get("passed") for case in cases}
    if outcomes.get(expected_failed_case) is not False:
        raise SystemExit(
            f"ablation did not fail expected case {expected_failed_case!r}: {task}"
        )
    if not any(passed is True for name, passed in outcomes.items() if name != expected_failed_case):
        raise SystemExit(f"ablation passed no unrelated case: {task}")
print(f"Mindustry Harbor {control} control passed: {task}")
PY
