local Transaction = {}
Transaction.__index = Transaction

local function valid_id(value)
    return type(value) == "string" and value ~= ""
end

local function positive_integer(value)
    return type(value) == "number" and value > 0 and value % 1 == 0
end

local function copy(value, seen)
    if type(value) ~= "table" then return value end
    seen = seen or {}
    if seen[value] ~= nil then return seen[value] end
    local result = {}
    seen[value] = result
    for key, item in pairs(value) do
        result[copy(key, seen)] = copy(item, seen)
    end
    return result
end

local function outcome(ok, code, state)
    return {
        ok = ok,
        code = code,
        state = state,
        duplicate = false,
    }
end

local function invoke(adapter, method, ...)
    local callback = adapter and adapter[method]
    if type(callback) ~= "function" then
        return nil, "adapter_error"
    end
    local ok, first, second = pcall(callback, ...)
    if not ok then return nil, "adapter_error" end
    return first, second
end

local function request_is_valid(request)
    return type(request) == "table"
        and valid_id(request.request_id)
        and valid_id(request.source_id)
        and valid_id(request.destination_id)
        and valid_id(request.pal_id)
        and positive_integer(request.count)
end

local function replay(record)
    local result = copy(record.result)
    result.duplicate = true
    return result
end

function Transaction.new(adapter, persisted)
    local self = setmetatable({}, Transaction)
    self.adapter = adapter or {}
    self.records = {}
    if type(persisted) == "table" and type(persisted.records) == "table" then
        self.records = copy(persisted.records)
    end
    return self
end

function Transaction.load(adapter, data)
    return Transaction.new(adapter, data)
end

function Transaction:_finish(record, result)
    record.state = result.state
    record.result = copy(result)
    return copy(result)
end

function Transaction:_reject(request_id, code)
    local result = outcome(false, code, "rejected")
    if valid_id(request_id) then
        self.records[request_id] = {
            state = "rejected",
            result = copy(result),
        }
    end
    return result
end

function Transaction:_compensate(record, code)
    -- Compensation deliberately runs in reverse mutation order.
    local destination_ok = invoke(
        self.adapter,
        "restore",
        record.request.destination_id,
        copy(record.destination_before))
    local source_ok = invoke(
        self.adapter,
        "restore",
        record.request.source_id,
        copy(record.source_before))

    if destination_ok and source_ok then
        return self:_finish(record, outcome(false, code or "adapter_error", "compensated"))
    end
    return self:_finish(record, outcome(false, "adapter_error", "unrecoverable"))
end

function Transaction:transfer(request)
    local request_id = type(request) == "table" and request.request_id or nil
    if valid_id(request_id) and self.records[request_id] ~= nil then
        return replay(self.records[request_id])
    end
    if not request_is_valid(request) then
        return self:_reject(request_id, "invalid_request")
    end
    if request.source_id == request.destination_id then
        return self:_reject(request_id, "same_container")
    end

    local source_before, source_error = invoke(self.adapter, "snapshot", request.source_id)
    if type(source_before) ~= "table" or type(source_before.entries) ~= "table" then
        return self:_reject(request_id, source_error or "adapter_error")
    end
    local destination_before, destination_error = invoke(
        self.adapter, "snapshot", request.destination_id)
    if type(destination_before) ~= "table" or type(destination_before.entries) ~= "table" then
        return self:_reject(request_id, destination_error or "adapter_error")
    end

    local available = 0
    for _, entry in ipairs(source_before.entries) do
        if type(entry) == "table" and entry.pal_id == request.pal_id then
            available = available + 1
        end
    end
    if available < request.count then
        return self:_reject(request_id, "insufficient_source")
    end

    local capacity, capacity_error = invoke(
        self.adapter, "capacity", request.destination_id, request.pal_id)
    if type(capacity) ~= "number" then
        return self:_reject(request_id, capacity_error or "adapter_error")
    end
    if capacity < request.count then
        return self:_reject(request_id, "insufficient_capacity")
    end

    local record = {
        request = copy(request),
        source_before = copy(source_before),
        destination_before = copy(destination_before),
        state = "prepared",
        result = outcome(false, "in_progress", "prepared"),
    }
    self.records[request_id] = record

    local removed, remove_error = invoke(
        self.adapter,
        "remove",
        request.source_id,
        request.pal_id,
        request.count)
    if type(removed) ~= "table" or #removed ~= request.count then
        return self:_compensate(record, remove_error or "adapter_error")
    end
    record.removed = copy(removed)
    record.state = "source_removed"

    local added, add_error = invoke(
        self.adapter,
        "add",
        request.destination_id,
        copy(removed))
    if added == nil or added == false then
        return self:_compensate(record, add_error or "adapter_error")
    end

    return self:_finish(record, {
        ok = true,
        code = "committed",
        state = "committed",
        request_id = request_id,
        moved = request.count,
        duplicate = false,
    })
end

function Transaction:status(request_id)
    if not valid_id(request_id) or self.records[request_id] == nil then
        return { ok = false, code = "unknown_request", state = "unknown" }
    end
    local record = self.records[request_id]
    local result = copy(record.result)
    result.state = record.state
    return result
end

function Transaction:recover()
    local recovered = 0
    local compensated = 0
    local unrecoverable = 0
    local identifiers = {}
    for request_id in pairs(self.records) do
        identifiers[#identifiers + 1] = request_id
    end
    table.sort(identifiers)

    for _, request_id in ipairs(identifiers) do
        local record = self.records[request_id]
        if record.state == "prepared" or record.state == "source_removed" then
            local result = self:_compensate(record, "recovered")
            recovered = recovered + 1
            if result.state == "compensated" then
                compensated = compensated + 1
            else
                unrecoverable = unrecoverable + 1
            end
        end
    end
    return {
        ok = unrecoverable == 0,
        recovered = recovered,
        compensated = compensated,
        unrecoverable = unrecoverable,
    }
end

function Transaction:save()
    return { records = copy(self.records) }
end

return Transaction
