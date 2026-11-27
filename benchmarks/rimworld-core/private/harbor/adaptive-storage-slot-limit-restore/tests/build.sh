#!/usr/bin/env bash
set -euo pipefail
umask 077
ulimit -f 65536
# .NET maps a large file for write-xor-execute memory, which any file-size limit
# kills with SIGXFSZ, so the build keeps the limit and turns that mapping off.
export DOTNET_EnableWriteXorExecute=0
readonly SUBMISSION=/submission/AdaptiveStorage
readonly WORK=/work
readonly OUTPUT=/output
mkdir -p "$WORK/obj/candidate" "$WORK/obj/verifier" "$WORK/dotnet" "$OUTPUT/candidate" "$OUTPUT/verifier"
cp -a /opt/rhenium/restore/candidate/. "$WORK/obj/candidate/"
cp -a /opt/rhenium/restore/verifier/. "$WORK/obj/verifier/"
# The restore tree is read-only in the image and cp -a keeps those modes.
chmod -R u+w "$WORK/obj"
dotnet build /opt/rhenium/tests/Submission.csproj --configuration Release --no-restore   -p:SubmissionRoot="$SUBMISSION" -p:BaseIntermediateOutputPath="$WORK/obj/candidate/" -p:OutputPath="$OUTPUT/candidate/"
dotnet build /opt/rhenium/tests/Harness/Harness.csproj --configuration Release --no-restore   -p:CandidateAssembly="$OUTPUT/candidate/AdaptiveStorage.dll"   -p:BaseIntermediateOutputPath="$WORK/obj/verifier/" -p:OutputPath="$OUTPUT/verifier/"
