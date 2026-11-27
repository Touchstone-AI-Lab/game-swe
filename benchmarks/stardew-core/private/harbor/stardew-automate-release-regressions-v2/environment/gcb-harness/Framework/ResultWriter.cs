using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace GcbHarness.Framework
{
    public sealed class CaseResult
    {
        public string Name { get; set; } = "";
        public bool Passed { get; set; }
        public string? Error { get; set; }
        public int Ticks { get; set; }
    }

    /// <summary>Writes the machine-readable verdict the verifier's reward gate parses.
    /// The JSON file is the single source of truth: if it is missing or malformed the
    /// gate must score 0, so this writer is deliberately boring — no partial writes
    /// (temp file + rename) and no dependence on game state.</summary>
    public static class ResultWriter
    {
        public static void Write(string path, string groupName, IReadOnlyList<CaseResult> results, string? fatal = null)
        {
            var payload = new
            {
                group = groupName,
                fatal,
                passed = results.Count(r => r.Passed),
                failed = results.Count(r => !r.Passed) + (fatal is null ? 0 : 1),
                cases = results,
            };
            string json = JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true });
            string tmp = path + ".tmp";
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
            File.WriteAllText(tmp, json);
            File.Move(tmp, path, overwrite: true);
        }
    }
}
