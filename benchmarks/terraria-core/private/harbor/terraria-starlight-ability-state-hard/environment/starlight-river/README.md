# Starlight River ability-state repair workspace

This source-only projection freezes Starlight River 0.2.9.4 at commit
`d367416dcadfe68a541a5821a0c4be86b42db219`. The retained production files
implement ability persistence, infusion slots, player cloning, delayed active
transitions, join progress, and remote start packets. Projection stubs expose
external engine and NetEasy contracts only.

Run `python tools/smoke.py` for a compile-only public check.
