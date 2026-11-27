#!/usr/bin/env bash
set -euo pipefail

control=${1:-all}
[[ $control == oracle || $control == ablation || $control == all ]] || {
  printf 'usage: validate-all.sh [oracle|ablation|all]\n' >&2
  exit 2
}

tasks=(
  build-quota-auditor
  power-grid-controller
  transactional-core-router
  unit-lease-scheduler
  wave-threat-arbiter
  item-reservation-ledger
  wave-budget-planner
  command-rate-limiter
  logic-link-registry
  core-failover-coordinator
)

for task in "${tasks[@]}"; do
  if [[ $control == oracle || $control == all ]]; then
    "$(dirname "$0")/validate-task.sh" "$task" oracle
  fi
  if [[ $control == ablation || $control == all ]]; then
    "$(dirname "$0")/validate-task.sh" "$task" ablation
  fi
done
