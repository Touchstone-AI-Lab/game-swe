local Transaction = require("palboxtransfer.transaction")

local PalboxTransferService = {}
PalboxTransferService.__index = PalboxTransferService

local function copy(value)
    if type(value) ~= "table" then return value end
    local result = {}
    for key, item in pairs(value) do result[key] = copy(item) end
    return result
end

local function container_id_of(object)
    if type(object) == "string" and object ~= "" then return object end
    if type(object) ~= "table" then return nil end
    if type(object.get) == "function" then
        local ok, unwrapped = pcall(object.get, object)
        if ok and unwrapped ~= nil and unwrapped ~= object then object = unwrapped end
    end
    if type(object.GetFullName) == "function" then
        local ok, value = pcall(object.GetFullName, object)
        if ok and value ~= nil then return tostring(value) end
    end
    return object.container_id or object.id
end

function PalboxTransferService.new(options)
    options = type(options) == "table" and options or {}
    local self = setmetatable({}, PalboxTransferService)
    self.containers = {}
    self.objects = {}
    self.external_adapter = options.adapter
    local adapter = options.adapter or {}
    if options.adapter == nil then
        function adapter.snapshot(id)
            local container = self.containers[id]
            if container == nil then return nil, "unknown_container" end
            return copy(container)
        end
        function adapter.capacity(id, _pal_id)
            local container = self.containers[id]
            if container == nil then return nil, "unknown_container" end
            return container.limit - #container.entries
        end
        function adapter.remove(id, pal_id, count)
            local container = self.containers[id]
            if container == nil then return nil, "unknown_container" end
            local removed, kept = {}, {}
            for _, entry in ipairs(container.entries) do
                if entry.pal_id == pal_id and #removed < count then
                    removed[#removed + 1] = entry
                else
                    kept[#kept + 1] = entry
                end
            end
            if #removed ~= count then return nil, "insufficient_source" end
            container.entries = kept
            return copy(removed)
        end
        function adapter.add(id, entries)
            local container = self.containers[id]
            if container == nil then return nil, "unknown_container" end
            for _, entry in ipairs(entries) do
                container.entries[#container.entries + 1] = copy(entry)
            end
            return copy(entries)
        end
        function adapter.restore(id, snapshot)
            self.containers[id] = copy(snapshot)
            return true
        end
    end
    self.adapter = adapter
    self.transaction = Transaction.new(adapter)
    return self
end

function PalboxTransferService:Track(object, stable_id, initial)
    local container_id = type(stable_id) == "string" and stable_id ~= ""
        and stable_id or container_id_of(object)
    if container_id == nil then return { ok = false, code = "invalid_container" } end
    self.objects[container_id] = object
    if self.external_adapter == nil and self.containers[container_id] == nil then
        initial = type(initial) == "table" and initial or {}
        self.containers[container_id] = {
            limit = type(initial.limit) == "number" and initial.limit or 40,
            entries = copy(initial.entries or {}),
        }
    end
    return { ok = true, container_id = container_id }
end

function PalboxTransferService:Transfer(request)
    return self.transaction:transfer(request)
end

function PalboxTransferService:Status(request_id)
    return self.transaction:status(request_id)
end

function PalboxTransferService:Recover()
    return self.transaction:recover()
end

function PalboxTransferService:Save()
    return {
        transaction = self.transaction:save(),
        containers = copy(self.containers),
    }
end

function PalboxTransferService:Load(data)
    data = type(data) == "table" and data or {}
    if self.external_adapter == nil and type(data.containers) == "table" then
        self.containers = copy(data.containers)
    end
    self.transaction = Transaction.load(self.adapter, data.transaction)
    return { ok = true }
end

return PalboxTransferService
