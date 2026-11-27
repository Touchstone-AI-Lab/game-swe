# ModLiquid Library map persistence repair workspace

This source-only projection freezes ModLiquid Library 2025.12.0.0 at commit
`282498893150b53d2e52efe26be0813aa8c8e193`. The retained production files
implement custom-liquid map-registry publication and runtime option selection,
the `.tlmap` header, sparse/RLE payload, transactional decoder, local/cloud
file lifecycle, and the real map IL integration points. Projection stubs expose
external engine and MonoMod contracts only.

Run `python tools/smoke.py` for a compile-only public check.
