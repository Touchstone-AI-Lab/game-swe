# Aequus carpentry replication repair workspace

This source-only projection freezes Aequus 2.7.3.3 at commit
`f823418776e7dd54b0f370e3ff1b4befc2bc857d`. The retained production files
implement carpenter completion persistence, building-buff validation and
serialization, world sync, packet authority, and player cloning. Projection
stubs expose external engine contracts only.

Run `python tools/smoke.py` for a compile-only public check.
