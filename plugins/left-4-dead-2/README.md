# Rhenium Left 4 Dead 2 plugin

This independent plugin discovers `left-4-dead-2` benchmark packs, materializes
source-only task workspaces, and evaluates full submissions in managed,
network-isolated Left 4 Dead 2 dedicated-server verifier images.

The plugin does not ship Valve game files. Prepare the public, anonymously
downloadable server runtime with:

```sh
rhenium auth login container
rhenium runtime prepare left-4-dead-2/l4d2-23990100-sourcemod-1.12.7246
```
