#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
rm -rf target
mkdir -p target/stubs target/classes
find compile-only -name '*.java' -print > target/stub-sources.txt
javac -J-Xmx256m -encoding UTF-8 -source 8 -target 8 -cp '/opt/sts/lib/*' -d target/stubs @target/stub-sources.txt
find src/main/java -name '*.java' -print > target/main-sources.txt
javac -g -J-Xmx768m -encoding UTF-8 -source 8 -target 8 -cp '/opt/sts/lib/*:target/stubs' -d target/classes @target/main-sources.txt
cp -a /opt/sts/downfall-resources/. target/classes/
jar cf target/Downfall.jar -C target/classes .
