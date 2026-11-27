local pricing=assert(SMODS.load_file('lib/pricing.lua'))()
SPC2_MODEL=assert(SMODS.load_file('lib/ledger.lua'))()(pricing)
assert(SMODS.load_file('adapter.lua'))()(SPC2_MODEL)
