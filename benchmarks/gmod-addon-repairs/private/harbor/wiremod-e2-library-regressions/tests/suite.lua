-- Behaviour-only assertions against Wiremod's Expression 2 standard library. Every case
-- compiles and runs a small Expression 2 program through the addon's own script
-- compiler (the path its e2test command uses); the program asserts on its own values.
local function runE2( code )
    local ok, fn = E2Lib.compileScript( code )
    if not ok then return "compile error: " .. tostring( fn ) end
    local ran, err = fn()
    if not ran then return "runtime error: " .. tostring( err ) end
    return "ok"
end

return {
    groupName = "Wiremod Expression 2 library",
    cases = {
        {   name = "sentinel: the addon and its script compiler are loaded",
            func = function()
                expect( WireLib ).to.exist()
                expect( E2Lib.compileScript ).to.beA( "function" )
                expect( runE2( "A = 1 + 1\nassert(A == 2)" ) ).to.equal( "ok" )
            end },

        {   name = "A: clamping a vector clamps every component",
            func = function()
                expect( runE2( [[
assert(clamp(vec(-5, 5, 50), vec(0, 0, 0), vec(10, 10, 10)) == vec(0, 5, 10))
assert(clamp(vec(1, 2, 3), vec(0, 0, 0), vec(10, 10, 10)) == vec(1, 2, 3))
assert(clamp(vec(20, -20, 5), vec(0, 0, 0), vec(10, 10, 10)) == vec(10, 0, 5))
]] ) ).to.equal( "ok" )
            end },

        {   name = "B: converting a fractional number to another base drops the fraction",
            func = function()
                expect( runE2( [[
assert(toString(10.5, 2) == "1010")
assert(toString(255.9, 16) == "FF")
assert(toString(-10.5, 2) == "-1010")
assert(toString(10, 2.5) == "1010")
]] ) ).to.equal( "ok" )
            end },

        {   name = "preserved: whole numbers still convert to other bases",
            func = function()
                expect( runE2( [[
assert(toString(255, 16) == "FF")
assert(toString(-10, 2) == "-1010")
assert(toString(35, 36) == "Z")
assert(toString(0, 2) == "0")
]] ) ).to.equal( "ok" )
            end },

        {   name = "C: complex numbers with a zero part print cleanly",
            func = function()
                expect( runE2( [[
assert(toString(comp(0, 3)) == "3i")
assert(toString(comp(0, -3)) == "-3i")
assert(toString(comp(5, 0)) == "5")
assert(toString(comp(0, 0)) == "0")
]] ) ).to.equal( "ok" )
            end },

        {   name = "preserved: complex numbers with both parts print as before",
            func = function()
                expect( runE2( [[
assert(toString(comp(2, -3)) == "2-3i")
assert(toString(comp(2, 3)) == "2+3i")
]] ) ).to.equal( "ok" )
            end },

        {   name = "D: an invalid character code yields an empty string",
            func = function()
                expect( runE2( [[
Nan = 0 / 0
S = toChar(Nan)
U = toUnicodeChar(Nan)
assert(S == "")
assert(U == "")
]] ) ).to.equal( "ok" )
            end },

        {   name = "preserved: character codes in and out of range behave as before",
            func = function()
                expect( runE2( [[
assert(toChar(65) == "A")
assert(toChar(300) == "")
assert(toUnicodeChar(65) == "A")
]] ) ).to.equal( "ok" )
            end },

        {   name = "E: a table built in a loop starts out the same every time",
            func = function()
                expect( runE2( [[
Bad = 0
for (I = 1, 3) {
    local T = table(10, 20, 30)
    if (T[3, number] != 30) { Bad++ }
    T:remove(1)
}
assert(Bad == 0)
]] ) ).to.equal( "ok" )
            end },

        {   name = "F: searching an array finds values of every type",
            func = function()
                expect( runE2( [[
A = array(vec2(1, 2), quat(3, 4, 5, 6), vec4(7, 8, 9, 10), comp(11, 12), matrix2(13, 14, 15, 16))
assert(A:indexOf(vec2(1, 2)) == 1)
assert(A:indexOf(quat(3, 4, 5, 6)) == 2)
assert(A:indexOf(vec4(7, 8, 9, 10)) == 3)
assert(A:indexOf(comp(11, 12)) == 4)
assert(A:indexOf(matrix2(13, 14, 15, 16)) == 5)
assert(A:indexOf(vec2(9, 9)) == 0)
]] ) ).to.equal( "ok" )
            end },

        {   name = "preserved: searching an array for numbers, strings and vectors",
            func = function()
                expect( runE2( [[
A = array(1, "two", vec(3, 3, 3), ang(4, 4, 4))
assert(A:indexOf(1) == 1)
assert(A:indexOf("two") == 2)
assert(A:indexOf(vec(3, 3, 3)) == 3)
assert(A:indexOf(ang(4, 4, 4)) == 4)
assert(A:indexOf("five") == 0)
]] ) ).to.equal( "ok" )
            end },
    },
}
