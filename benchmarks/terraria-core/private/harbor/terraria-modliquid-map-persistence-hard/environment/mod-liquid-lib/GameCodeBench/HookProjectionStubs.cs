using System;
using System.Collections.Generic;

namespace Microsoft.Xna.Framework
{
    public readonly struct Color : IEquatable<Color>
    {
        public int Value { get; }
        public Color(int value) => Value = value;
        public bool Equals(Color other) => Value == other.Value;
        public override bool Equals(object obj) => obj is Color other && Equals(other);
        public override int GetHashCode() => Value;
    }
}
namespace Terraria.ID
{
    public static class LiquidID { public static int Count = 4; }
}

namespace MonoMod.Cil
{
    public enum MoveType { Before, After }

    public sealed class Instruction
    {
        public string Kind { get; init; }
        public string Owner { get; init; }
        public string Member { get; init; }
        public int Number { get; init; }

        public static Instruction Ldloc(int index) => new() { Kind = "ldloc", Number = index };
        public static Instruction Ldloca(int index) => new() { Kind = "ldloca", Number = index };
        public static Instruction Ldarg(int index) => new() { Kind = "ldarg", Number = index };
        public static Instruction Ldsfld(string owner, string field) => new() { Kind = "ldsfld", Owner = owner, Member = field };
        public static Instruction Stsfld(string owner, string field) => new() { Kind = "stsfld", Owner = owner, Member = field };
        public static Instruction Stloc(int index) => new() { Kind = "stloc", Number = index };
        public static Instruction Add() => new() { Kind = "add" };
        public static Instruction Ldelem() => new() { Kind = "ldelem" };
        public static Instruction Stelem() => new() { Kind = "stelem" };
        public static Instruction LdcI4(int value) => new() { Kind = "ldc.i4", Number = value };
        public static Instruction Newobj(string owner, string constructor = ".ctor") => new() { Kind = "newobj", Owner = owner, Member = constructor };
        public static Instruction Call(string owner, string method) => new() { Kind = "call", Owner = owner, Member = method };
        public static Instruction Other() => new() { Kind = "other" };

        public bool MatchLdloc(out int index) { index = Number; return Kind == "ldloc"; }
        public bool MatchLdloc(int index) => Kind == "ldloc" && Number == index;
        public bool MatchLdloca(out int index) { index = Number; return Kind == "ldloca"; }
        public bool MatchLdarg(int index) => Kind == "ldarg" && Number == index;
        public bool MatchCall(string owner, string method) => Kind == "call" && Owner == owner && Member == method;
        public bool MatchNewobj<T>(string constructor) => Kind == "newobj" && Member == constructor && (Owner == null || Owner == typeof(T).FullName);
        public bool MatchLdsfld(string owner, string field) => Kind == "ldsfld" && Owner == owner && Member == field;
        public bool MatchStsfld(string owner, string field) => Kind == "stsfld" && Owner == owner && Member == field;
        public bool MatchStloc(out int index) { index = Number; return Kind == "stloc"; }
        public bool MatchAdd() => Kind == "add";
        public bool MatchLdelemAny<T>() => Kind == "ldelem";
        public bool MatchStelemAny<T>() => Kind == "stelem";
        public bool MatchLdcI4(int value) => Kind == "ldc.i4" && Number == value;
    }

    public sealed class EmittedOperation
    {
        public string Kind { get; init; }
        public object Value { get; init; }
    }

    public sealed class ILContext
    {
        public List<Instruction> Instructions { get; } = new();
        public List<EmittedOperation> Emitted { get; } = new();

        public ILContext(params Instruction[] instructions) => Instructions.AddRange(instructions);
    }

    public sealed class ILCursor
    {
        private readonly ILContext _context;
        private int _index;

        public ILCursor(ILContext context) => _context = context;

        public bool TryGotoNext(MoveType moveType, params Func<Instruction, bool>[] predicates)
        {
            for (int start = _index; start + predicates.Length <= _context.Instructions.Count; start++)
            {
                bool matches = true;
                for (int offset = 0; offset < predicates.Length; offset++)
                    matches &= predicates[offset](_context.Instructions[start + offset]);
                if (!matches) continue;
                _index = moveType == MoveType.After ? start + predicates.Length : start;
                return true;
            }
            return false;
        }

        public void GotoNext(MoveType moveType, params Func<Instruction, bool>[] predicates)
        {
            if (!TryGotoNext(moveType, predicates))
                throw new InvalidOperationException("IL anchor not found.");
        }

        public void EmitLdloc(int index) => _context.Emitted.Add(new() { Kind = "ldloc", Value = index });
        public void EmitLdloca(int index) => _context.Emitted.Add(new() { Kind = "ldloca", Value = index });
        public void EmitLdarg(int index) => _context.Emitted.Add(new() { Kind = "ldarg", Value = index });
        public void EmitDelegate<TDelegate>(TDelegate callback) where TDelegate : Delegate
            => _context.Emitted.Add(new() { Kind = "delegate", Value = callback });
    }
}
