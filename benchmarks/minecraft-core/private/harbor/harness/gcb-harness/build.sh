#!/usr/bin/env bash
# Builds gcb-harness.jar with plain javac/jar (no Gradle, no third-party libraries).
# Usage: build.sh <classpath-file> <output-jar>
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <classpath-file> <output-jar>" >&2
  exit 2
fi

classpath_file="$1"
output_jar="$2"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -r "$classpath_file" ]; then
  echo "classpath file not readable: $classpath_file" >&2
  exit 2
fi

# The classpath file lists jars one per line or already colon-joined; accept both.
classpath="$(tr '\n' ':' < "$classpath_file" | sed -e 's/::*/:/g' -e 's/^://' -e 's/:$//')"
if [ -z "$classpath" ]; then
  echo "classpath file is empty: $classpath_file" >&2
  exit 2
fi

build_dir="$(mktemp -d)"
trap 'rm -rf "$build_dir"' EXIT
classes_dir="$build_dir/classes"
mkdir -p "$classes_dir"

sources=()
while IFS= read -r -d '' source; do
  sources+=("$source")
done < <(find "$script_dir/src/main/java" -type f -name '*.java' -print0 | sort -z)
if [ "${#sources[@]}" -eq 0 ]; then
  echo "no Java sources found under $script_dir/src/main/java" >&2
  exit 2
fi

javac --release 21 -proc:none -Xlint:none -encoding UTF-8 \
  -cp "$classpath" -d "$classes_dir" "${sources[@]}"
cp -R "$script_dir/src/main/resources/." "$classes_dir/"

mkdir -p "$(dirname "$output_jar")"
jar --create --file "$output_jar" -C "$classes_dir" .
echo "built $output_jar"
