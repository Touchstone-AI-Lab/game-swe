using System;
using System.Collections.Generic;
using System.Linq;

namespace GcbHarness.Framework
{
    /// <summary>Thrown by assertions; the pump records the message as the case failure.</summary>
    public sealed class GcbAssertException : Exception
    {
        public GcbAssertException(string message) : base(message) { }
    }

    /// <summary>Minimal expect-style assertions. Messages must state observed vs
    /// expected so a verifier log is diagnosable without rerunning.</summary>
    public static class GcbAssert
    {
        public static void IsTrue(bool condition, string what)
        {
            if (!condition)
                throw new GcbAssertException($"expected: {what}");
        }

        public static void AreEqual<T>(T expected, T actual, string what)
        {
            if (!EqualityComparer<T>.Default.Equals(expected, actual))
                throw new GcbAssertException($"{what}: expected {Render(expected)}, got {Render(actual)}");
        }

        public static void IsNotNull(object? value, string what)
        {
            if (value is null)
                throw new GcbAssertException($"{what}: expected non-null");
        }

        public static void Contains<T>(IEnumerable<T> haystack, Func<T, bool> predicate, string what)
        {
            if (!haystack.Any(predicate))
                throw new GcbAssertException($"{what}: no matching element");
        }

        public static void Succeeds(Action action, string what)
        {
            try
            {
                action();
            }
            catch (Exception ex)
            {
                throw new GcbAssertException($"{what}: threw {ex.GetType().Name}: {ex.Message}");
            }
        }

        private static string Render(object? value)
        {
            return value switch
            {
                null => "null",
                string s => $"\"{s}\"",
                _ => value.ToString() ?? value.GetType().Name,
            };
        }
    }
}
