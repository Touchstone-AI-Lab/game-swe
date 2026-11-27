#!/usr/bin/env bash
set -euo pipefail

root="/workspace/magic-storage/Common/IO"
oracle="$(cd "$(dirname "$0")" && pwd)/after/Common/IO"

for file in BitBuffer128.cs ValueReader.cs ValueWriter.cs StringCompressor.cs NetCompression.NetIO.cs; do
  cp "$oracle/$file" "$root/$file"
done
