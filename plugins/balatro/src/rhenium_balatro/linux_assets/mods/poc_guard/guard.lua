-- Runs before Steamodded preflight and before any game initialization.
-- This is accidental-state protection for inspected code, NOT a sandbox.
local function norm(s) return (s:gsub('\\', '/'):gsub('/+$', ''):lower()) end
local expected = assert(os.getenv('POC_SAVE_DIR'), 'Missing POC_SAVE_DIR')
local mods = assert(os.getenv('LOVELY_MOD_DIR'), 'Missing LOVELY_MOD_DIR')
local run = assert(os.getenv('POC_RUN_DIR'), 'Missing POC_RUN_DIR')
local function fatal(message)
    local f = io.open(run .. '/guard-error.txt', 'w')
    if f then f:write(message); f:close() end
    os.exit(70)
end
if norm(love.filesystem.getSaveDirectory()) ~= norm(expected) then
    fatal('Actual save directory differs from expected; aborted before game initialization')
end
if norm(require('lovely').mod_dir) ~= norm(mods) then
    fatal('Actual mod directory differs from expected')
end
if norm(love.filesystem.getAppdataDirectory()) ~= norm(os.getenv('APPDATA')) then
    fatal('Actual appdata directory differs from expected')
end
local marker = assert(os.getenv('POC_NONCE'))
assert(love.filesystem.write('poc-isolation-probe.txt', marker))
local f = assert(io.open(expected .. '/poc-isolation-probe.txt', 'r'))
assert(f:read('*a') == marker, 'Filesystem marker not at expected physical location')
f:close()
local evidence = assert(io.open(run .. '/isolation.txt', 'w'))
evidence:write(love.filesystem.getSaveDirectory(), '\n', require('lovely').mod_dir, '\n',
               love.filesystem.getAppdataDirectory(), '\n', love.getVersion(), '\n', marker)
evidence:close()
if os.getenv('POC_PROBE_ONLY') == '1' then os.exit(0) end
