#!/bin/bash
# Stage the private suite over the submission and report a single graded result.
set -uo pipefail
mkdir -p /logs/verifier

EXPECTED=16
SRC=/app/modthespire
SUITE="$SRC/src/test/java/gcb"

rm -rf "$SUITE" && mkdir -p "$SUITE"
cp /tests/Target.java /tests/TargetPatch.java /tests/ByRefBoxingTest.java /tests/ModRecordTest.java /tests/EarlyReturnTarget.java /tests/TakeOverPatch.java /tests/GradePatch.java /tests/PlainPrefix.java /tests/SilencePatch.java /tests/EarlyReturnTest.java /tests/PostfixTarget.java /tests/PostfixReplace.java /tests/PostfixObserve.java /tests/PostfixPatchTest.java "$SUITE/"

cd "$SRC" || exit 1
# `clean` is load-bearing: the image ships compiled classes and a submission copied in
# with older timestamps would otherwise be judged up to date and never recompiled, so the
# verifier would grade stale artifacts rather than the submission.
mvn -B -o clean test > /logs/verifier/maven.log 2>&1
status=$?

line=$(grep -oE "Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+, Skipped: [0-9]+" /logs/verifier/maven.log | tail -1)
echo "entrypoint_exit=$status $line" > /logs/verifier/summary.txt

ok=0
if [ "$status" -eq 0 ] && echo "$line" | grep -qE "Tests run: $EXPECTED, Failures: 0, Errors: 0"; then
  ok=1
fi
echo "$ok" > /logs/verifier/reward.txt
cat /logs/verifier/summary.txt
exit 0
