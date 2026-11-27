using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using MagicStorage.Common.IO;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace GcbMagicStorage;

public sealed class VerifierSystem : ModSystem
{
    private sealed record CaseOutcome(string Name, bool Passed, string? Error);

    private static readonly LengthCompressor<uint> FrameTiers = new(
        EncodingTier.CreateZero<uint>(prefix: 0, prefixBitCount: 1, size: 131072)
    );

    public override void PostSetupContent()
    {
        string? reportPath = Environment.GetEnvironmentVariable("GCB_TERRARIA_REPORT");
        if (string.IsNullOrWhiteSpace(reportPath)) return;
        var outcomes = new[]
        {
            Run("real_engine_nested_binary_frame", NestedBinaryFrame),
            Run("real_engine_long_string_full_width_scalar", LongStringAndScalar),
            Run("real_engine_vanilla_item_metadata", VanillaItemMetadata),
        };
        bool passed = outcomes.All(outcome => outcome.Passed);
        var report = new
        {
            schemaVersion = 1,
            complete = true,
            passed,
            terrariaVersion = Main.versionNumber,
            tModLoaderVersion = BuildInfo.tMLVersion.ToString(),
            dedicatedServer = Main.dedServ,
            cases = outcomes.Select(outcome => new
            {
                name = outcome.Name,
                status = outcome.Passed ? "passed" : "failed",
                error = outcome.Error,
            }),
        };
        Directory.CreateDirectory(Path.GetDirectoryName(reportPath)!);
        File.WriteAllText(reportPath, JsonSerializer.Serialize(report));
        Environment.Exit(passed && Main.dedServ ? 0 : 90);
    }

    private static CaseOutcome Run(string name, Action test)
    {
        try { test(); return new(name, true, null); }
        catch (Exception error) { return new(name, false, error.ToString()); }
    }

    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static byte[] Encode(Action<ValueWriter> write)
    {
        using var stream = new MemoryStream();
        var writer = new ValueWriter(stream);
        write(writer);
        writer.Flush();
        return stream.ToArray();
    }

    private static ValueReader Reader(byte[] bytes)
        => new(new BinaryReader(new MemoryStream(bytes, writable: false)));

    private static void NestedBinaryFrame()
    {
        byte[] bytes = Encode(writer =>
        {
            using (writer.CreateScope(FrameTiers, optimizeForBytes: false))
            {
                writer.Write((byte)0b011, 3);
                using (writer.CreateScope(FrameTiers, optimizeForBytes: true))
                    writer.Write((ushort)0xCAFE, 16);
                writer.Write((byte)0b10110, 5);
            }
            writer.Write((byte)0xE7, 8);
        });
        ValueReader reader = Reader(bytes);
        using (reader.ReadScope(FrameTiers, optimizeForBytes: false))
        {
            Check(reader.ReadByte(3) == 0b011, "parent prefix changed");
            using (reader.ReadScope(FrameTiers, optimizeForBytes: true))
                Check(reader.ReadUInt16(16) == 0xCAFE, "nested payload changed");
            Check(reader.ReadByte(5) == 0b10110, "parent suffix changed");
        }
        Check(reader.ReadByte(8) == 0xE7, "outer sentinel changed");
    }

    private static void LongStringAndScalar()
    {
        string expected = string.Concat(Enumerable.Repeat("A界🙂", 1200));
        const long scalar = unchecked((long)0x8ACE13572468BDF1UL);
        byte[] bytes = Encode(writer =>
        {
            StringCompressor.WriteTo(writer, expected);
            writer.Write(scalar, 64);
            writer.Write((byte)0x2B, 6);
        });
        ValueReader reader = Reader(bytes);
        Check(StringCompressor.ReadFrom(reader) == expected, "long UTF-8 string changed");
        Check(reader.ReadInt64(64) == scalar, "full-width signed scalar changed");
        Check(reader.ReadByte(6) == 0x2B, "scalar sentinel changed");
    }

    private static void VanillaItemMetadata()
    {
        var expected = new Item(ItemID.StoneBlock, 25001) { favorited = true };
        using var stream = new MemoryStream();
        var writer = new ValueWriter(stream);
        using (writer.CreateScope(NetCompression.lengthTiers, optimizeForBytes: false))
        {
            ModContent.GetInstance<ItemTypeTracker>().Send(expected, writer);
            ModContent.GetInstance<ItemPrefixTracker>().Send(expected, writer);
            writer.Write(false);
            writer.Write7BitEncodedInt(expected.stack / expected.maxStack);
            writer.Write((uint)(expected.stack % expected.maxStack), NetCompression.GetBitSize(expected.maxStack));
            writer.Write(expected.favorited);
        }
        writer.Flush();

        stream.Position = 0;
        var reader = new ValueReader(new BinaryReader(stream));
        IDisposable scope = reader.ReadScope(NetCompression.lengthTiers, optimizeForBytes: false);
        MethodInfo receiveMetadata = typeof(NetCompression).GetMethod(
            "ReceiveItemMetadata",
            BindingFlags.NonPublic | BindingFlags.Static
        ) ?? throw new MissingMethodException(typeof(NetCompression).FullName, "ReceiveItemMetadata");
        object?[] arguments = { reader, new Item(), true, true, new DeserializedNetItem() };
        try
        {
            receiveMetadata.Invoke(null, arguments);
        }
        catch (TargetInvocationException error)
        {
            throw new InvalidOperationException(
                "real Terraria metadata decoder threw",
                error.InnerException ?? error
            );
        }
        scope.Dispose();
        var actual = (Item)arguments[1]!;
        var data = (DeserializedNetItem)arguments[4]!;

        Check(actual.type == expected.type, "real Terraria item type changed");
        Check(actual.stack == expected.stack, "overfull real Terraria item stack changed");
        Check(actual.favorited, "real Terraria favorite flag changed");
        Check(data.stack == expected.stack, "deserialized stack metadata changed");
    }
}
