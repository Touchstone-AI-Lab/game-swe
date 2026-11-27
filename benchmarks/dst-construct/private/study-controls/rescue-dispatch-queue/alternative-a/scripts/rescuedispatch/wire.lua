-- Text format shared by the server component (encode) and the replica
-- (decode). Identifiers never contain control characters, so TAB separates
-- fields and LF separates rows.
--   Q <target> <effective severity> <x> <z>
--   L <lease> <target> <helper> <expires at, whole seconds>
-- Request/volunteer history is never part of this format.

local Wire = {}

Wire.ROW_LIMIT = 16

local function whole(value)
    if type(value) ~= "number" or value ~= value then
        return "0"
    end
    return string.format("%d", math.floor(value + 0.5))
end

function Wire.encode(snapshot, places)
    local rows = {}
    local queue = snapshot.queue or {}
    for index = 1, math.min(#queue, Wire.ROW_LIMIT) do
        local entry = queue[index]
        local place = places ~= nil and places[entry.target_id] or nil
        rows[#rows + 1] = table.concat({
            "Q", entry.target_id, whole(entry.effective_severity),
            whole(place ~= nil and place.x or 0), whole(place ~= nil and place.z or 0),
        }, "\t")
    end
    local leases = snapshot.leases or {}
    for index = 1, math.min(#leases, Wire.ROW_LIMIT) do
        local lease = leases[index]
        rows[#rows + 1] = table.concat({
            "L", lease.lease_id, lease.target_id, lease.helper_id, whole(lease.expires_at),
        }, "\t")
    end
    return table.concat(rows, "\n")
end

local function fields_of(row)
    local fields = {}
    for field in string.gmatch(row, "[^\t]+") do
        fields[#fields + 1] = field
    end
    return fields
end

function Wire.decode(text)
    local view = { queue = {}, leases = {} }
    if type(text) ~= "string" then
        return view
    end
    for row in string.gmatch(text, "[^\n]+") do
        local fields = fields_of(row)
        if fields[1] == "Q" and #fields == 5 then
            view.queue[#view.queue + 1] = {
                target_id = fields[2],
                effective_severity = tonumber(fields[3]),
                x = tonumber(fields[4]),
                z = tonumber(fields[5]),
            }
        elseif fields[1] == "L" and #fields == 5 then
            view.leases[#view.leases + 1] = {
                lease_id = fields[2],
                target_id = fields[3],
                helper_id = fields[4],
                expires_at = tonumber(fields[5]),
            }
        end
    end
    return view
end

return Wire
