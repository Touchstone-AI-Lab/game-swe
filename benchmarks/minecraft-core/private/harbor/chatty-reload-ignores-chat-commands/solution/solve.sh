#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/plugin
cp -a /solution/after/. /app/plugin/
echo "oracle: applied the reference repair to the plugin source tree"
