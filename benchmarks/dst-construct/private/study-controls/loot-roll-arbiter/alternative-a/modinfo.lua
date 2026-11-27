name = "Loot Roll Arbiter"
description = "Server authoritative need / greed / pass loot rolls with a public, reproducible dice generator."
author = "Rhenium"
version = "1.0.0"

api_version = 10

dst_compatible = true
dont_starve_compatible = false
reign_of_giants_compatible = false
shipwrecked_compatible = false

-- The world entity gains a network variable, so every client needs the mod.
all_clients_require_mod = true
client_only_mod = false

server_filter_tags = { "loot roll" }

configuration_options = {}
