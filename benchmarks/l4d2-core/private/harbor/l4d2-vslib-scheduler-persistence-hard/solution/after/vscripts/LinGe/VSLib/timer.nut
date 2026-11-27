/*  
 * Copyright (c) 2013 LuKeM aka Neil - 119 and Rayman1103
 * 
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software
 * and associated documentation files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use, copy, modify, merge, publish,
 * distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 * 
 * The above copyright notice and this permission notice shall be included in all copies or
 * substantial portions of the Software.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
 * BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
 * DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 * 
 */


/**
 * \brief A timer system to call a function after a certain amount of time.
 *
 *  The Timer table allows the developer to easily add synchronized callbacks.
 */
if (!("Timers" in ::VSLib))
{
	::VSLib.Timers <-
	{
		TimersList = {}
		TimersID = {}
		ClockList = {}
		count = 0
	}
}

/*
 * Constants
 */

// Passable constants
getconsttable()["NO_TIMER_PARAMS"] <- null; /** No timer params */

// Internal constants
const UPDATE_RATE = 0.1; /** Fastest possible update rate */

// Flags
getconsttable()["TIMER_FLAG_KEEPALIVE"] <- (1 << 1); /** Keep timer alive even after RoundEnd is called */
getconsttable()["TIMER_FLAG_COUNTDOWN"] <- (1 << 2); /** Fire the timer the specified number of times before the timer removes itself */
getconsttable()["TIMER_FLAG_DURATION"] <- (1 << 3); /** Fire the timer each interval for the specified duration */
getconsttable()["TIMER_FLAG_DURATION_VARIANT"] <- (1 << 4); /** Fire the timer each interval for the specified duration, regardless of internal function call time loss */


/**
 * Creates a named timer that will be added to the timers list. If a named timer already exists,
 * it will be replaced.
 *
 * @return Name of the created timer
 */
function VSLib::Timers::AddTimerByName(strName, delay, repeat, func, paramTable = null, flags = 0, value = {})
{
    local id = ::VSLib.Timers.AddTimer(delay, repeat, func, paramTable, flags, value);
    if (id == -1) return -1;
    ::VSLib.Timers.RemoveTimerByName(strName);
    ::VSLib.Timers.TimersID[strName] <- id;
    return strName;
}

/**
 * Deletes a named timer.
 */
function VSLib::Timers::RemoveTimerByName(strName)
{
    if (strName in ::VSLib.Timers.TimersID)
        ::VSLib.Timers.RemoveTimer(::VSLib.Timers.TimersID[strName]);
}

/**
 * Calls a function and passes the specified table to the callback after the specified delay.
 */
function VSLib::Timers::AddTimer(delay, repeat, func, paramTable = null, flags = 0, value = {})
{
    local numeric = function(v) { return typeof v == "integer" || typeof v == "float"; };
    if (!numeric(delay) || typeof func != "function" || typeof value != "table"
        || (typeof repeat != "bool" && typeof repeat != "integer") || typeof flags != "integer") return -1;
    // Ordinary callbacks accept opaque payloads used by MoreSI and LinGe events.
    // Only modes that write TimerCount require a table (null creates one).
    if ((flags & (4 | 8)) && paramTable != null && typeof paramTable != "table") return -1;
    local modes = 0;
    foreach (flag in [4, 8, 16]) if (flags & flag) modes++;
    if (modes > 1) return -1;
    if ((flags & 4) && (!("count" in value) || typeof value.count != "integer" || value.count <= 0)) return -1;
    if ((flags & (8 | 16)) && (!("duration" in value) || !numeric(value.duration) || value.duration < 0)) return -1;
    delay = delay.tofloat();
    if (delay < UPDATE_RATE) delay = UPDATE_RATE;
    local options = clone value;
    if (flags & 8)
    {
        flags = (flags & ~8) | 4;
        options.count <- floor(options.duration / delay).tointeger();
    }
    if (paramTable == null) paramTable = {};
    ++count;
    TimersList[count] <- {
        _delay = delay, _func = func, _params = paramTable,
        _startTime = Time(), _baseTime = Time(), _repeat = repeat.tointeger() > 0,
        _flags = flags, _opval = options
    };
    return count;
}

/**
 * Removes the specified timer.
 */
function VSLib::Timers::RemoveTimer(idx)
{
    if (idx in TimersList) delete TimersList[idx];
    local names = [];
    foreach (name, id in TimersID) if (id == idx) names.append(name);
    foreach (name in names) delete TimersID[name];
}

/**
 * Manages VSLib timers.
 */
function VSLib::Timers::_SettleClock(timer, now)
{
    local elapsed = now - timer._lastUpdateTime;
    if (elapsed > 0)
    {
        if (timer._command == 1) timer._value += elapsed;
        else if (timer._command == 2)
        {
            timer._value -= elapsed;
            if (!timer._allowNegTimer && timer._value < 0) timer._value = 0;
        }
        timer._lastUpdateTime = now;
    }
}

function VSLib::Timers::ManageTimer(idx, command, value = null, allowNegTimer = false)
{
    local now = Time();
    if (idx in ClockList && value == null)
    {
        _SettleClock(ClockList[idx], now);
        ClockList[idx]._command = command;
        ClockList[idx]._allowNegTimer = allowNegTimer;
    }
    else
        ClockList[idx] <- { _value = value == null ? 0 : value, _startTime = now,
            _lastUpdateTime = now, _command = command, _allowNegTimer = allowNegTimer };
}

/**
 * Returns the value of a VSLib timer.
 */
function VSLib::Timers::ReadTimer(idx)
{
    if (!(idx in ClockList)) return null;
    _SettleClock(ClockList[idx], Time());
    return ClockList[idx]._value;
}

/**
 * Returns a VSLib timer as a displayable string --:--.
 */
function VSLib::Timers::DisplayTime(idx)
{
	return ::VSLib.Utils.GetDisplayTime(::VSLib.Timers.ReadTimer(idx));
}

/**
 * Manages all timers and provides interface for custom updates.
 */
::VSLib.Timers._thinkFunc <- function()
{
    if (!("VSLib" in getroottable())) return;
    local timers = ::VSLib.Timers;
    local now = Time(), snapshot = [];
    foreach (id, timer in timers.TimersList) snapshot.append([id, timer]);
    foreach (entry in snapshot)
    {
        local id = entry[0], timer = entry[1];
        if (!(id in timers.TimersList) || timers.TimersList[id] != timer) continue;
        if (now - timer._startTime < timer._delay) continue;
        if (((timer._flags & 4) && timer._opval.count <= 0)
            || ((timer._flags & 16) && now - timer._baseTime > timer._opval.duration))
        { timers.RemoveTimer(id); continue; }
        if (timer._flags & 4)
        {
            timer._params.TimerCount <- timer._opval.count;
            if (--timer._opval.count <= 0) timer._repeat = false;
        }
        try { if (timer._func(timer._params) == false) timer._repeat = false; }
        catch (error)
        {
            printl("VSLib timer retired after callback failure: " + error);
            timers.RemoveTimer(id);
            continue;
        }
        if (!(id in timers.TimersList) || timers.TimersList[id] != timer) continue;
        if (timer._repeat) timer._startTime = now;
        else timers.RemoveTimer(id);
    }
    foreach (name, clock in timers.ClockList) timers._SettleClock(clock, now);
}

/*
 * Create a think timer
 */
if (!("_thinkTimer" in ::VSLib.Timers))
{
	::VSLib.Timers._thinkTimer <- SpawnEntityFromTable("info_target", { targetname = "vslib_timer" });
	if (::VSLib.Timers._thinkTimer != null)
	{
		::VSLib.Timers._thinkTimer.ValidateScriptScope();
		local scrScope = ::VSLib.Timers._thinkTimer.GetScriptScope();
		scrScope["ThinkTimer"] <- ::VSLib.Timers._thinkFunc;
		AddThinkToEnt(::VSLib.Timers._thinkTimer, "ThinkTimer");
	}
	else
		throw "VSLib Error: Timer system could not be created; Could not create dummy entity";
}


// Add a weakref
::Timers <- ::VSLib.Timers.weakref();