# Frozen source and dependencies

Target source is from `fbef0102/L4D1_2-Plugins` commit
`b570e9efd9534ea8822f6fc7909704b4ee8fcdf2` under `l4dinfectedbots/` and
`spawn_infected_nolimit/`. Upstream compiled `.smx` files and screenshots were
removed. The source is distributed under `GPL-3.0-only`; `LICENSE` has SHA-256
`230184f60bae2feaf244f10a8bac053c8ff33a183bcc365b4d8b876d2b7f4809`.

`third_party/include/left4dhooks_bundle/` contains the public compile-time
Left4DHooks includes from `SilvDev/Left4DHooks` commit
`3d44e2207d8ec1218f46667e2c05e4f127a5fb74`. Its `GPL-3.0-only` license is
preserved as `third_party/LEFT4DHOOKS-LICENSE`, SHA-256
`230184f60bae2feaf244f10a8bac053c8ff33a183bcc365b4d8b876d2b7f4809`.

`third_party/include/multicolors*` contains Multi-Colors headers from
`Bara/Multi-Colors` commit `7e39d040139a8a05cdc5bf792bec40df982cda33`.
Its `GPL-3.0-only` license is preserved as `third_party/MULTICOLORS-LICENSE`,
SHA-256 `53927bd0b739d38c87a0a82236fd9b070c2dfff11c0c119be50372005d5047ad`.
These are source-only dependencies; the private verifier builds runtime plugins
independently.
