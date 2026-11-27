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
* File I/O functions that simplify the saving and loading of data.
*/
::VSLib.FileIO <- {};


// Data-only persistence; never evaluate the input as Squirrel code.
::VSLib.FileIO._Quote <- function(text)
{
    local out = "\"";
    for (local i = 0; i < text.len(); i++)
    {
        local ch = text.slice(i, i + 1);
        if (ch == "\"") out += "\\\"";
        else if (ch == "\\") out += "\\\\";
        else if (ch == "\n") out += "\\n";
        else if (ch == "\r") out += "\\r";
        else if (ch == "\t") out += "\\t";
        else out += ch;
    }
    return out + "\"";
}

::VSLib.FileIO._Encode <- function(value, ancestors)
{
    local kind = typeof value;
    if (value == null) return "null";
    if (kind == "bool") return value ? "true" : "false";
    if (kind == "integer") return value.tostring();
    if (kind == "string") return ::VSLib.FileIO._Quote(value);
    if (kind == "float")
    {
        if (value != value || value > 3.402823466e38 || value < -3.402823466e38) throw "nonfinite number";
        local out = format("%.9g", value);
        if (out.find(".") == null && out.find("e") == null && out.find("E") == null) out += ".0";
        return out;
    }
    if (kind != "table" && kind != "array") throw "unsupported persistent value";
    foreach (ancestor in ancestors) if (ancestor == value) throw "cyclic persistent value";
    ancestors.append(value);
    local out = kind == "table" ? "{\n" : "[\n";
    foreach (key, item in value)
    {
        if (kind == "table")
        {
            if (typeof key != "string" && typeof key != "integer") throw "unsupported persistent key";
            out += "[" + ::VSLib.FileIO._Encode(key, ancestors) + "] = ";
        }
        out += ::VSLib.FileIO._Encode(item, ancestors) + ",\n";
    }
    ancestors.pop();
    return out + (kind == "table" ? "}" : "]");
}

::VSLib.FileIO._DataReader <- class
{
    text = null;
    pos = 0;
    constructor(input) { text = input; }
    function Peek() { return pos < text.len() ? text.slice(pos, pos + 1) : ""; }
    function Space()
    {
        while (pos < text.len() && (Peek() == " " || Peek() == "\n" || Peek() == "\t" || Peek() == "\r")) pos++;
    }
    function Take(wanted)
    {
        Space();
        if (Peek() != wanted) throw "unexpected data token";
        pos++;
    }
    function String()
    {
        Take("\"");
        local out = "";
        while (pos < text.len())
        {
            local ch = Peek(); pos++;
            if (ch == "\"") return out;
            if (ch == "\\")
            {
                if (pos == text.len()) throw "truncated string";
                ch = Peek(); pos++;
                if (ch == "n") out += "\n";
                else if (ch == "r") out += "\r";
                else if (ch == "t") out += "\t";
                else if (ch == "\\" || ch == "\"") out += ch;
                else throw "invalid escape";
            }
            else if (ch == "\n" || ch == "\r") throw "unescaped newline";
            else out += ch;
        }
        throw "unterminated string";
    }
    function Word()
    {
        Space();
        local start = pos;
        while (pos < text.len())
        {
            local ch = Peek();
            if (ch == " " || ch == "\n" || ch == "\t" || ch == "\r" || ch == "," || ch == "=" || ch == "}" || ch == "]") break;
            pos++;
        }
        if (pos == start) throw "missing token";
        return text.slice(start, pos);
    }
    function Value()
    {
        Space();
        local ch = Peek();
        if (ch == "\"") return String();
        if (ch == "{")
        {
            pos++;
            local result = {};
            Space();
            while (Peek() != "}")
            {
                local key;
                if (Peek() == "[")
                {
                    pos++; key = Value(); Take("]");
                    if (typeof key != "string" && typeof key != "integer") throw "invalid key";
                }
                else
                {
                    key = Word();
                    if (!regexp("^[a-zA-Z_][a-zA-Z0-9_]*$").match(key)) throw "invalid legacy key";
                }
                Take("=");
                if (key in result) throw "duplicate key";
                result[key] <- Value();
                Space();
                if (Peek() == ",") { pos++; Space(); }
                if (pos >= text.len()) throw "truncated table";
            }
            pos++;
            return result;
        }
        if (ch == "[")
        {
            pos++;
            local result = [];
            Space();
            while (Peek() != "]")
            {
                result.append(Value());
                Space();
                if (Peek() == ",") { pos++; Space(); }
                if (pos >= text.len()) throw "truncated array";
            }
            pos++;
            return result;
        }
        local token = Word();
        if (token == "true") return true;
        if (token == "false") return false;
        if (token == "null") return null;
        if (!regexp("^-?(0|[1-9][0-9]*)([.][0-9]+)?([eE][+-]?[0-9]+)?$").match(token)) throw "invalid scalar";
        if (token.find(".") != null || token.find("e") != null || token.find("E") != null)
        {
            local number = token.tofloat();
            if (number != number || number > 3.402823466e38 || number < -3.402823466e38) throw "nonfinite number";
            return number;
        }
        return token.tointeger();
    }
}

function VSLib::FileIO::SerializeTable(object, predicateStart = "{\n", predicateEnd = "}\n", indice = true)
{
    return "// VSLib2\n" + ::VSLib.FileIO._Encode(object, []);
}

function VSLib::FileIO::SaveTable(fileName, object)
{
    try
    {
        if (typeof object != "table" && typeof object != "array") return false;
        local encoded = ::VSLib.FileIO.SerializeTable(object);
        return StringToFile(fileName + ".tbl", encoded);
    }
    catch (error) { return false; }
}

function VSLib::FileIO::DeserializeReviseTable(object)
{
    local kind = typeof object;
    if (kind == "string")
        return ::VSLib.Utils.StringReplace(::VSLib.Utils.StringReplace(object, "{VSQUOTE}", "\""), "{VSSLASH}", "\\");
    if (kind != "table" && kind != "array") return object;
    local result = kind == "table" ? {} : [];
    foreach (key, value in object)
    {
        local decoded = ::VSLib.FileIO.DeserializeReviseTable(value);
        if (kind == "array") result.append(decoded);
        else
        {
            if (typeof key == "string" && regexp("^_vslInt_(0|[1-9][0-9]*)$").match(key)) key = key.slice(8).tointeger();
            if (key in result) throw "colliding legacy key";
            result[key] <- decoded;
        }
    }
    return result;
}

function VSLib::FileIO::LoadTable(fileName)
{
    try
    {
        local text = FileToString(fileName + ".tbl");
        if (text == null || text.len() == 0) return null;
        local modern = text.len() >= 10 && text.slice(0, 10) == "// VSLib2\n";
        if (modern) text = text.slice(10);
        local reader = ::VSLib.FileIO._DataReader(text);
        local result = reader.Value();
        reader.Space();
        if (reader.pos != text.len() || (typeof result != "table" && typeof result != "array")) return null;
        return modern ? result : ::VSLib.FileIO.DeserializeReviseTable(result);
    }
    catch (error) { return null; }
}


/**
 * This function will make the filename unique for each mapname.
 * @authors Rayman1103
 */
function VSLib::FileIO::MakeFileName( mapname, modename )
{
	return "VSLib_" + mapname + "_" + modename;
}

/**
 * This function will serialize and save a table to the hard disk from the current mapname; useful for storing stats,
 * round times, and other important information individually for every mapname.
 * @authors Rayman1103
 */
function VSLib::FileIO::SaveTableFileName(mapname, modename, table)
{
	return ::VSLib.FileIO.SaveTable(::VSLib.FileIO.MakeFileName( mapname, modename ), table);
}

/**
 * This function will deserialize and return the compiled table from the current mapname.
 * If the table does not exist, null is returned.
 * @authors Rayman1103
 */
function VSLib::FileIO::LoadTableFileName(mapname, modename)
{
	return ::VSLib.FileIO.LoadTable(::VSLib.FileIO.MakeFileName( mapname, modename ));
}



// Add a weak reference to the global table.
::FileIO <- ::VSLib.FileIO.weakref();