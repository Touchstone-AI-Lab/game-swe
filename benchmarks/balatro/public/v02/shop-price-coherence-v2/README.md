# Reviewed local submission — protocol v2

Read CONTRACT.md and any listed public API documents. Keep the exported package unchanged. Copy its entire starter directory to a separate candidate directory; edit only the Lua paths listed in package.json's editable_files. Preserve every immutable file and the manifest. Missing files, additional files, links/junctions and oversized inputs are rejected. File layout is an explicit interface, not a measure of difficulty.

The operator reviews the complete candidate tree and seals its hash through `python -m poc.scale10_v2 --protocol v2 submit --package <original-package> --candidate <edited-copy> --reviewed-sha256 <reviewed-tree-hash> --out <new-directory>`. Scoring uses the separately installed, fixed licensed Windows environment and private operator assets. A successful public-file check is not engine acceptance. Every required case, response, process cleanup and input-integrity check must complete.

Only self-authored reviewed code is permitted in this local workflow. Sealing is not an untrusted-code sandbox. The public package contains no reference answers, private tests, raw traces, saves or game/dependency contents. Tasks are authored repair exercises, not claims of upstream historical bugs. Target difficulty is a design label; model calibration is unmeasured and formal integration is not implemented.
