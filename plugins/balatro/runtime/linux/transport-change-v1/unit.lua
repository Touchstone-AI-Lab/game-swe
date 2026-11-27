-- Pure unit doubles only. No game, socket connection, dependency edit or candidate.
local source = assert(io.open(PROPOSAL_PATH, 'rb')):read('*a')
local function scenario(sends, clock, selection, expected, indices)
  local calls, waits = {}, 0
  local client = {}
  function client:send(data, first)
    assert(data == 'abcdefghij')
    calls[#calls+1] = first
    local row = assert(sends[#calls])
    return row[1], row[2], row[3]
  end
  local ticks = 0
  local environment = {
    BB_SERVER = {client_socket=client},
    sendDebugMessage = function() end,
    socket = {
      gettime = function() ticks=ticks+1; return clock[ticks] or clock[#clock] end,
      select = function(readable, writable, timeout)
        assert(#readable==0 and writable[1]==client and timeout>0 and timeout<=1)
        waits=waits+1
        if selection then return {},{},selection end
        return {},{client},nil
      end,
    },
  }
  setmetatable(environment,{__index=_G})
  local load = assert(loadstring(source..'\nreturn send_raw'))
  setfenv(load,environment)
  assert(load()('abcdefghij') == expected)
  assert(#calls==#indices)
  for i,v in ipairs(indices)do assert(calls[i]==v)end
  return waits
end
assert(scenario({{10}}, {0}, nil, true, {1})==0)
assert(scenario({{nil,'timeout',4},{10}}, {0,.01,.02}, nil, true, {1,5})==1)
assert(scenario({{nil,'timeout',0},{nil,'timeout',7},{10}}, {0,.01,.02,.03,.04}, nil, true, {1,1,8})==2)
assert(scenario({{nil,'closed',4}}, {0}, nil, false, {1})==0)
assert(scenario({{nil,'timeout',4}}, {0,2}, nil, false, {1})==0)
assert(scenario({{nil,'timeout',4}}, {0,.01}, 'timeout', false, {1})==1)
assert(scenario({{nil,'timeout',99}}, {0}, nil, false, {1})==0)
assert(scenario({{4}}, {0}, nil, false, {1})==0)
return true
