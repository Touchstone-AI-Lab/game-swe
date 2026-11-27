-- Proposed only: replace send_raw in a separately versioned, approved derived copy.
-- The original non-blocking socket mode and HTTP/JSON serialization are retained.
local function send_raw(response_str)
  local client = BB_SERVER.client_socket
  if not client then return false end
  local deadline = socket.gettime() + 1.0
  local first = 1
  local function failed(reason)
    sendDebugMessage("Failed to send response: " .. tostring(reason), "BB.SERVER")
    return false
  end
  while first <= #response_str do
    local sent, err, partial = client:send(response_str, first)
    if sent then
      if sent ~= #response_str then return failed("invalid send index") end
      return true
    end
    if err ~= "timeout" then return failed(err) end
    if type(partial) ~= "number" or partial % 1 ~= 0 or partial < first - 1 or partial > #response_str then
      return failed("invalid partial-send index")
    end
    first = partial + 1
    if first > #response_str then return true end
    local remaining = deadline - socket.gettime()
    if remaining <= 0 then return failed("write deadline") end
    local _, writable, select_error = socket.select({}, {client}, remaining)
    if select_error or not writable or #writable ~= 1 or writable[1] ~= client then
      return failed(select_error or "socket not writable")
    end
    if socket.gettime() >= deadline then return failed("write deadline") end
  end
  return true
end
