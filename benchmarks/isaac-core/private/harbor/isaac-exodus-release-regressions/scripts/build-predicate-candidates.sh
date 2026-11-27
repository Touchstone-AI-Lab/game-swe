#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 BROKEN_EXODUS_DIR OUTPUT_DIR" >&2
  exit 2
}

[ "$#" -eq 2 ] || usage
base_dir=$(cd "$1" && pwd)
output_dir=$2
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
task_dir=$(cd "$script_dir/.." && pwd)
gold_patch="$task_dir/solution/gold.patch"

[ -f "$base_dir/main.lua" ] || usage
[ -f "$gold_patch" ] || usage
mkdir -p "$output_dir"

extract_hunks() {
  local destination=$1
  local wanted=$2
  awk -v wanted=",${wanted}," '
    BEGIN { hunk = 0; emit = 1 }
    /^@@/ {
      hunk += 1
      emit = index(wanted, "," hunk ",") > 0
    }
    hunk == 0 || emit { print }
  ' "$gold_patch" >"$destination"
}

build_candidate() {
  local report=$1
  local hunks=$2
  local candidate="$output_dir/$report"
  local fragment="$output_dir/$report.patch"
  mkdir -p "$candidate"
  cp "$base_dir/main.lua" "$candidate/main.lua"
  extract_hunks "$fragment" "$hunks"
  patch --batch --fuzz=0 --ignore-whitespace --silent -d "$candidate" -p1 <"$fragment"
  rm "$fragment"
}

build_candidate EX-184 14
build_candidate EX-191 17
perl -pi -e \
  's/ItemVariables\.TRAGIC_MUSHROOM\.Uses = ItemVariables\.TRAGIC_MUSHROOM\.Uses \+ 1/ItemVariables.TRAGIC_MUSHROOM.Used = true/' \
  "$output_dir/EX-191/main.lua"
build_candidate EX-203 3
build_candidate EX-217 15
build_candidate EX-226 10,11
build_candidate EX-239 12
build_candidate EX-247 4,20,21,22,23
build_candidate EX-251 9
build_candidate EX-258 25
build_candidate EX-266 8
build_candidate EX-274 18,19
build_candidate EX-281 24
build_candidate EX-289 32
build_candidate EX-296 7
build_candidate EX-303 1,16
perl -pi -e \
  's/MUTANT_CLOVER = \{ Used = 0 \}/MUTANT_CLOVER = { Used = false }/' \
  "$output_dir/EX-303/main.lua"
perl -pi -e \
  's/ItemVariables\.TRAGIC_MUSHROOM\.Used = true/ItemVariables.TRAGIC_MUSHROOM.Uses = ItemVariables.TRAGIC_MUSHROOM.Uses + 1/' \
  "$output_dir/EX-303/main.lua"
build_candidate EX-311 1,26,27,28
perl -pi -e \
  's/TRAGIC_MUSHROOM = \{ Uses = 0 \}/TRAGIC_MUSHROOM = { Used = false }/' \
  "$output_dir/EX-311/main.lua"
build_candidate EX-318 2,29
build_candidate EX-327 13
build_candidate EX-335 5,6
build_candidate EX-342 30,31

candidate_count=$(find "$output_dir" -mindepth 1 -maxdepth 1 -type d -name 'EX-*' | wc -l | tr -d ' ')
if [ "$candidate_count" -ne 20 ]; then
  echo "expected 20 predicate candidates, found $candidate_count" >&2
  exit 1
fi

for candidate in "$output_dir"/EX-*; do
  if cmp -s "$base_dir/main.lua" "$candidate/main.lua"; then
    echo "candidate did not change main.lua: $candidate" >&2
    exit 1
  fi
done

sha256sum "$output_dir"/EX-*/main.lua
