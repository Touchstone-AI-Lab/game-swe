using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using MagicStorage.Common.IO;
using Terraria;
using Terraria.ModLoader;

internal static class Program {
	private sealed class CheckFailedException(string message) : Exception(message);
	private sealed class ThrowingModItem : ModItem {
		public override void NetReceive(BinaryReader reader) {
			reader.ReadByte();
			throw new InvalidDataException("mod payload rejected");
		}
	}

	private sealed class RecordingGlobalItem(byte expected, bool throws = false) : GlobalItem {
		public static readonly List<byte> Received = [];

		public override void NetReceive(Item item, BinaryReader reader) {
			byte value = reader.ReadByte();
			Equal(expected, value, "global payload value");
			Received.Add(value);
			if (throws)
				throw new InvalidDataException("global payload rejected");
		}
	}

	private sealed class SendingModItem(byte[] payload, bool throws = false) : ModItem {
		public int Calls { get; private set; }

		public override void NetSend(BinaryWriter writer) {
			Calls++;
			writer.Write(payload);
			if (throws)
				throw new InvalidDataException("mod send rejected");
		}
	}

	private sealed class SendingGlobalItem(byte[] payload, bool throws = false) : GlobalItem {
		public int Calls { get; private set; }

		public override void NetSend(Item item, BinaryWriter writer) {
			Calls++;
			writer.Write(payload);
			if (throws)
				throw new InvalidDataException("global send rejected");
		}
	}

	private static readonly LengthCompressor<uint> FrameTiers = new(
		EncodingTier.CreateZero<uint>(prefix: 0, prefixBitCount: 1, size: 131072)
	);

	private static readonly IReadOnlyDictionary<string, Action> Cases = BuildCases();

	private static int Main(string[] args) {
		if (args.Length != 1 || !Cases.TryGetValue(args[0], out Action test)) {
			Console.Error.WriteLine("expected exactly one known case name");
			return 2;
		}

		try {
			test();
			Console.WriteLine("PASS");
			return 0;
		} catch (Exception error) {
			Console.Error.WriteLine(error);
			return 1;
		}
	}

	private static IReadOnlyDictionary<string, Action> BuildCases() {
		Dictionary<string, Action> cases = new(StringComparer.Ordinal) {
			["scope-flat-bit-frame-compat"] = ScopeFlatBitFrame,
			["scope-empty-child-keeps-parent-active"] = ScopeEmptyChildKeepsParentActive,
			["scope-empty-child-counts-flag"] = ScopeEmptyChildCountsFlag,
			["scope-nonempty-bit-child-counted"] = ScopeNonEmptyBitChildCounted,
			["scope-nonempty-byte-child-counted"] = ScopeNonEmptyByteChildCounted,
			["scope-two-child-frames"] = ScopeTwoChildFrames,
			["scope-three-level-roundtrip"] = ScopeThreeLevelRoundTrip,
			["u64-reader-aligned-max"] = () => ReadIndependentU64(0, 0, ulong.MaxValue, 0x15, 5),
			["u64-reader-high-pattern"] = () => ReadIndependentU64(0, 0, 0x8000_0000_0000_0042UL, 0x2A, 6),
			["u64-reader-keeps-sentinel"] = () => ReadIndependentU64(0, 0, 0x0123_4567_89AB_CDEFUL, 0xD, 4),
			["double-reader-preserves-bits"] = DoubleReaderPreservesBits,
			["u64-writer-aligned-compat"] = () => CompareWriterU64(0, 0, 0xFEDC_BA98_7654_3210UL, 0xB, 4),
			["u64-writer-offset-1"] = () => CompareWriterU64(1, 1, 0x8000_0000_0000_0001UL, 0x35, 6),
			["u64-writer-offset-2"] = () => CompareWriterU64(2, 2, 0xF000_0000_0000_0042UL, 0x15, 5),
			["u64-writer-offset-4"] = () => CompareWriterU64(4, 0xB, 0x8123_4567_89AB_CDEFUL, 0x6D, 7),
			["u64-writer-offset-7"] = () => CompareWriterU64(7, 0x65, 0xFFFF_0000_0000_0001UL, 0xA, 4),
			["u64-writer-two-adjacent-values"] = WriterTwoAdjacentU64,
			["signed-int-min-full-width"] = () => SignedIntRoundTrip(int.MinValue, 32),
			["signed-int-negative-pattern-full-width"] = () => SignedIntRoundTrip(unchecked((int)0x8ACE_1357), 32),
			["signed-int-partial-31-bit"] = () => SignedIntRoundTrip(-1234567, 31),
			["signed-long-min-full-width"] = () => SignedLongRoundTrip(long.MinValue, 64),
			["signed-long-negative-pattern-full-width"] = () => SignedLongRoundTrip(unchecked((long)0x8ACE_1357_2468_BDF1UL), 64),
			["signed-long-partial-40-bit"] = () => SignedLongRoundTrip(-0x12_3456_789L, 40),
			["signed-long-partial-63-bit"] = () => SignedLongRoundTrip(-0x1234_5678_9ABC_DEF, 63),
			["signed-positive-and-zero-width-guards"] = SignedPositiveAndZeroWidthGuards,
			["string-ascii-2047-guard"] = () => StringRoundTrip(new string('a', 2047), 0x5A),
			["string-ascii-2048-boundary"] = () => StringRoundTrip(new string('b', 2048), 0xA5),
			["string-ascii-2049"] = () => StringRoundTrip(new string('c', 2049), 0x3C),
			["string-ascii-4096"] = () => StringRoundTrip(new string('d', 4096), 0xC3),
			["string-unicode-4096"] = () => StringRoundTrip(string.Concat(Enumerable.Repeat("存档", 2048)), 0x96),
			["string-unicode-mixed-large"] = () => StringRoundTrip(string.Concat(Enumerable.Repeat("A界🙂", 1200)), 0x69),
			["string-max-representable-length"] = () => StringRoundTrip(new string('z', ushort.MaxValue), 0x7E),
			["string-oversize-65536-rejected"] = () => OversizedStringRejected(new string('x', 65536)),
			["string-oversize-unicode-rejected"] = () => OversizedStringRejected(string.Concat(Enumerable.Repeat("界", 70000))),
			["string-oversize-rejection-is-atomic"] = OversizedStringRejectionIsAtomic,
			["item-partial-stack-roundtrip"] = () => ItemRoundTrip(stack: 37, maxStack: 9999, prefix: 0, favorite: false),
			["item-exact-max-stack-roundtrip"] = () => ItemRoundTrip(stack: 9999, maxStack: 9999, prefix: 0, favorite: false),
			["item-overfull-stack-roundtrip"] = () => ItemRoundTrip(stack: 25001, maxStack: 9999, prefix: 0, favorite: false),
			["item-custom-max-stack-roundtrip"] = () => ItemRoundTrip(stack: 577, maxStack: 250, prefix: 0, favorite: false),
			["item-prefix-favorite-and-stack-roundtrip"] = () => ItemRoundTrip(stack: 1234, maxStack: 9999, prefix: 73, favorite: true),
			["item-read-stack-false-preserved"] = ItemReadStackFalsePreserved,
			["item-mixed-list-roundtrip"] = ItemMixedListRoundTrip,
			["item-zero-overflow-quotient-isolated"] = () => InvalidOverflowItemIsolated(0),
			["item-overflow-arithmetic-isolated"] = () => InvalidOverflowItemIsolated(int.MaxValue),
			["seven-bit-int-max-roundtrip"] = () => SevenBitRoundTrip(int.MaxValue, 0x41),
			["seven-bit-int-min-roundtrip"] = () => SevenBitRoundTrip(int.MinValue, 0x52),
			["seven-bit-negative-one-roundtrip"] = () => SevenBitRoundTrip(-1, 0x63),
			["seven-bit-final-group-overflow-rejected"] = () => InvalidSevenBitRejected([0x80, 0x80, 0x80, 0x80, 0x10, 0x74], 0x74),
			["seven-bit-final-group-high-pattern-rejected"] = () => InvalidSevenBitRejected([0xFF, 0xFF, 0xFF, 0xFF, 0x70, 0x85], 0x85),
			["seven-bit-sixth-group-rejected"] = () => InvalidSevenBitRejected([0x80, 0x80, 0x80, 0x80, 0x80, 0x96], 0x96),
			["item-missing-mod-payload-drained"] = ItemMissingModPayloadDrained,
			["item-missing-mod-still-reads-global"] = ItemMissingModStillReadsGlobal,
			["item-throwing-mod-still-reads-global"] = ItemThrowingModStillReadsGlobal,
			["item-throwing-global-does-not-skip-later-global"] = ItemThrowingGlobalDoesNotSkipLaterGlobal,
			["send-item-binary-mod-failure-atomic"] = SendItemBinaryModFailureAtomic,
			["send-item-binary-global-failure-atomic"] = SendItemBinaryGlobalFailureAtomic,
			["send-item-value-writer-misaligned-reusable"] = SendItemValueWriterMisalignedReusable,
			["send-item-inside-parent-scope-reusable"] = SendItemInsideParentScopeReusable,
			["send-item-success-format-compatible"] = SendItemSuccessFormatCompatible,
			["send-item-hooks-called-once"] = SendItemHooksCalledOnce,
			["send-items-binary-middle-failure-atomic"] = SendItemsBinaryMiddleFailureAtomic,
			["send-items-value-writer-middle-failure-atomic"] = SendItemsValueWriterMiddleFailureAtomic,
			["send-items-inside-parent-scope-reusable"] = SendItemsInsideParentScopeReusable,
			["send-items-global-after-mod-failure-atomic"] = SendItemsGlobalAfterModFailureAtomic,
			["scope-out-of-order-nonempty-recoverable"] = ScopeOutOfOrderNonEmptyRecoverable,
			["scope-out-of-order-empty-recoverable"] = ScopeOutOfOrderEmptyRecoverable,
			["scope-out-of-order-three-level-recoverable"] = ScopeOutOfOrderThreeLevelRecoverable,
			["scope-double-close-still-rejected"] = ScopeDoubleCloseStillRejected,
		};
		return cases;
	}

	private static byte[] Encode(Action<ValueWriter> write) {
		using MemoryStream stream = new();
		ValueWriter writer = new(stream);
		write(writer);
		writer.Flush();
		return stream.ToArray();
	}

	private static ValueReader Reader(byte[] bytes) => new(new BinaryReader(new MemoryStream(bytes, writable: false)));

	private static void ScopeFlatBitFrame() {
		byte[] bytes = Encode(writer => {
			using (writer.CreateScope(FrameTiers, optimizeForBytes: false))
				writer.Write((byte)0b10101, 5);
			writer.Write((byte)0xA5, 8);
		});
		ValueReader reader = Reader(bytes);
		using (reader.ReadScope(FrameTiers, optimizeForBytes: false))
			Equal((byte)0b10101, reader.ReadByte(5), "flat payload");
		Equal((byte)0xA5, reader.ReadByte(8), "flat sentinel");
	}

	private static void ScopeEmptyChildKeepsParentActive() => NestedScopeRoundTrip(
		childBytes: false,
		childPayloadBits: 0,
		first: 0b101,
		last: 0b11010
	);

	private static void ScopeEmptyChildCountsFlag() {
		byte[] bytes = Encode(writer => {
			using (writer.CreateScope(FrameTiers, optimizeForBytes: false)) {
				using (writer.CreateScope(FrameTiers, optimizeForBytes: false)) { }
			}
			writer.Write((byte)0xD3, 8);
		});
		ValueReader reader = Reader(bytes);
		using (reader.ReadScope(FrameTiers, optimizeForBytes: false))
			using (reader.ReadScope(FrameTiers, optimizeForBytes: false)) { }
		Equal((byte)0xD3, reader.ReadByte(8), "empty-frame sentinel");
	}

	private static void ScopeNonEmptyBitChildCounted() => NestedScopeRoundTrip(
		childBytes: false,
		childPayloadBits: 11,
		first: 0b011,
		last: 0b10110
	);

	private static void ScopeNonEmptyByteChildCounted() => NestedScopeRoundTrip(
		childBytes: true,
		childPayloadBits: 16,
		first: 0b111,
		last: 0b00101
	);

	private static void NestedScopeRoundTrip(bool childBytes, int childPayloadBits, byte first, byte last) {
		byte[] bytes = Encode(writer => {
			using (writer.CreateScope(FrameTiers, optimizeForBytes: false)) {
				writer.Write(first, 3);
				using (writer.CreateScope(FrameTiers, optimizeForBytes: childBytes)) {
					if (childPayloadBits > 0)
						writer.Write(0x6B5u, childPayloadBits);
				}
				writer.Write(last, 5);
			}
			writer.Write((byte)0xE7, 8);
		});

		ValueReader reader = Reader(bytes);
		using (reader.ReadScope(FrameTiers, optimizeForBytes: false)) {
			Equal(first, reader.ReadByte(3), "parent prefix");
			using (reader.ReadScope(FrameTiers, optimizeForBytes: childBytes)) {
				if (childPayloadBits > 0)
					Equal(0x6B5u & Mask32(childPayloadBits), reader.ReadUInt32(childPayloadBits), "child payload");
			}
			Equal(last, reader.ReadByte(5), "parent suffix");
		}
		Equal((byte)0xE7, reader.ReadByte(8), "outer sentinel");
	}

	private static void ScopeTwoChildFrames() {
		byte[] bytes = Encode(writer => {
			using (writer.CreateScope(FrameTiers, false)) {
				using (writer.CreateScope(FrameTiers, false))
					writer.Write((byte)0x1B, 5);
				using (writer.CreateScope(FrameTiers, true))
					writer.Write((ushort)0xCAFE, 16);
				writer.Write((byte)0x6, 3);
			}
			writer.Write((byte)0x91, 8);
		});
		ValueReader reader = Reader(bytes);
		using (reader.ReadScope(FrameTiers, false)) {
			using (reader.ReadScope(FrameTiers, false))
				Equal((byte)0x1B, reader.ReadByte(5), "first child");
			using (reader.ReadScope(FrameTiers, true))
				Equal((ushort)0xCAFE, reader.ReadUInt16(16), "second child");
			Equal((byte)0x6, reader.ReadByte(3), "parent tail");
		}
		Equal((byte)0x91, reader.ReadByte(8), "sibling sentinel");
	}

	private static void ScopeThreeLevelRoundTrip() {
		byte[] bytes = Encode(writer => {
			using (writer.CreateScope(FrameTiers, false)) {
				writer.Write(true);
				using (writer.CreateScope(FrameTiers, false)) {
					writer.Write((byte)0x5, 3);
					using (writer.CreateScope(FrameTiers, true))
						writer.Write((uint)0xDEAD_BEEF, 32);
					writer.Write(false);
				}
				writer.Write((byte)0xA, 4);
			}
			writer.Write((byte)0x42, 8);
		});
		ValueReader reader = Reader(bytes);
		using (reader.ReadScope(FrameTiers, false)) {
			True(reader.ReadBoolean(), "level one prefix");
			using (reader.ReadScope(FrameTiers, false)) {
				Equal((byte)0x5, reader.ReadByte(3), "level two prefix");
				using (reader.ReadScope(FrameTiers, true))
					Equal(0xDEAD_BEEFu, reader.ReadUInt32(32), "level three payload");
				False(reader.ReadBoolean(), "level two suffix");
			}
			Equal((byte)0xA, reader.ReadByte(4), "level one suffix");
		}
		Equal((byte)0x42, reader.ReadByte(8), "three-level sentinel");
	}

	private static void ReadIndependentU64(int prefixBits, ulong prefix, ulong value, ulong sentinel, int sentinelBits) {
		byte[] bytes = PackBits((prefix, prefixBits), (value, 64), (sentinel, sentinelBits));
		ValueReader reader = Reader(bytes);
		if (prefixBits > 0)
			Equal(prefix, reader.ReadUInt64(prefixBits), "prefix");
		Equal(value, reader.ReadUInt64(64), "64-bit payload");
		Equal(sentinel, reader.ReadUInt64(sentinelBits), "following sentinel");
	}

	private static void DoubleReaderPreservesBits() {
		ulong bits = BitConverter.DoubleToUInt64Bits(-Math.PI * 1.0e240);
		byte[] bytes = PackBits((bits, 64), (0x2D, 6));
		ValueReader reader = Reader(bytes);
		double actual = BitConverter.UInt64BitsToDouble(reader.ReadUInt64(64));
		Equal(bits, BitConverter.DoubleToUInt64Bits(actual), "double bits");
		Equal(0x2DUL, reader.ReadUInt64(6), "double sentinel");
	}

	private static void CompareWriterU64(int prefixBits, ulong prefix, ulong value, ulong sentinel, int sentinelBits) {
		byte[] actual = Encode(writer => {
			if (prefixBits > 0)
				writer.Write(prefix, prefixBits);
			writer.Write(value, 64);
			writer.Write(sentinel, sentinelBits);
		});
		byte[] expected = PackBits((prefix, prefixBits), (value, 64), (sentinel, sentinelBits));
		SequenceEqual(expected, actual, "writer bytes");
	}

	private static void WriterTwoAdjacentU64() {
		ulong first = 0x8000_0000_0000_0001UL;
		ulong second = 0xFEDC_BA98_7654_3210UL;
		byte[] actual = Encode(writer => {
			writer.Write(first, 64);
			writer.Write(second, 64);
			writer.Write((byte)0x5, 3);
		});
		SequenceEqual(PackBits((first, 64), (second, 64), (5, 3)), actual, "adjacent u64 bytes");
	}

	private static void SignedIntRoundTrip(int value, int bits) {
		byte[] bytes = Encode(writer => {
			writer.Write(value, bits);
			writer.Write((byte)0x15, 5);
		});
		ValueReader reader = Reader(bytes);
		Equal(value, reader.ReadInt32(bits), "signed int");
		Equal((byte)0x15, reader.ReadByte(5), "signed int sentinel");
	}

	private static void SignedLongRoundTrip(long value, int bits) {
		byte[] bytes = Encode(writer => {
			writer.Write(value, bits);
			writer.Write((byte)0x2B, 6);
		});
		ValueReader reader = Reader(bytes);
		Equal(value, reader.ReadInt64(bits), "signed long");
		Equal((byte)0x2B, reader.ReadByte(6), "signed long sentinel");
	}

	private static void SignedPositiveAndZeroWidthGuards() {
		byte[] bytes = Encode(writer => {
			writer.Write(0, 0);
			writer.Write(0L, 0);
			writer.Write(0x1234_5678, 32);
			writer.Write(0x0123_4567_89AB_CDEFL, 64);
		});
		ValueReader reader = Reader(bytes);
		Equal(0, reader.ReadInt32(0), "zero-width int");
		Equal(0L, reader.ReadInt64(0), "zero-width long");
		Equal(0x1234_5678, reader.ReadInt32(32), "positive int");
		Equal(0x0123_4567_89AB_CDEFL, reader.ReadInt64(64), "positive long");
	}

	private static void StringRoundTrip(string value, byte sentinel) {
		byte[] bytes = Encode(writer => {
			StringCompressor.WriteTo(writer, value);
			writer.Write(sentinel, 8);
		});
		ValueReader reader = Reader(bytes);
		Equal(value, StringCompressor.ReadFrom(reader), "compressed string");
		Equal(sentinel, reader.ReadByte(8), "string sentinel");
	}

	private static void OversizedStringRejected(string value) {
		using MemoryStream stream = new();
		ValueWriter writer = new(stream);
		Throws<ArgumentOutOfRangeException>(() => StringCompressor.WriteTo(writer, value));
		Equal(0L, stream.Length, "oversize write touched stream");
	}

	private static void OversizedStringRejectionIsAtomic() {
		using MemoryStream stream = new();
		ValueWriter writer = new(stream);
		Throws<ArgumentOutOfRangeException>(() => StringCompressor.WriteTo(writer, new string('q', 65536)));
		StringCompressor.WriteTo(writer, "after-rejection");
		writer.Write((byte)0xC7, 8);
		writer.Flush();
		ValueReader reader = Reader(stream.ToArray());
		Equal("after-rejection", StringCompressor.ReadFrom(reader), "valid string after rejection");
		Equal((byte)0xC7, reader.ReadByte(8), "atomicity sentinel");
	}

	private static void ItemRoundTrip(int stack, int maxStack, int prefix, bool favorite) {
		const int type = 101;
		ItemDefinitions.SetMaxStack(type, maxStack);
		byte[] packet = BuildRawItemPacket(type, stack, maxStack, prefix, favorite, writeStack: true);
		Item result = NetCompression.ReceiveItem(new BinaryReader(new MemoryStream(packet, writable: false)));
		False(result.IsFailure, "valid item became failure item");
		Equal(type, result.type, "item type");
		Equal(stack, result.stack, "item stack");
		Equal(prefix, result.prefix, "item prefix");
		Equal(favorite, result.favorited, "item favorite");
	}

	private static void ItemReadStackFalsePreserved() {
		const int type = 102;
		ItemDefinitions.SetMaxStack(type, 9999);
		byte[] packet = BuildRawItemPacket(type, 777, 9999, 12, favorite: true, writeStack: false);
		Item result = NetCompression.ReceiveItem(
			new BinaryReader(new MemoryStream(packet, writable: false)),
			readStack: false,
			readFavorite: true
		);
		Equal(1, result.stack, "readStack=false default");
		Equal(12, result.prefix, "readStack=false prefix");
		True(result.favorited, "readStack=false favorite");
	}

	private static void ItemMixedListRoundTrip() {
		ItemDefinitions.SetMaxStack(111, 9999);
		ItemDefinitions.SetMaxStack(112, 250);
		ItemDefinitions.SetMaxStack(113, 1);
		List<Item> source = [
			new Item(111, 3, 4),
			new Item(112, 777, 5) { favorited = true },
			new Item(113, 1, 6),
		];
		using MemoryStream stream = new();
		NetCompression.SendItems(source, new BinaryWriter(stream));
		stream.Position = 0;
		List<Item> result = NetCompression.ReceiveItems(new BinaryReader(stream));
		Equal(source.Count, result.Count, "item list count");
		for (int i = 0; i < source.Count; i++) {
			Equal(source[i].type, result[i].type, $"item {i} type");
			Equal(source[i].stack, result[i].stack, $"item {i} stack");
			Equal(source[i].prefix, result[i].prefix, $"item {i} prefix");
			Equal(source[i].favorited, result[i].favorited, $"item {i} favorite");
		}
	}

	private static void InvalidOverflowItemIsolated(int quotient) {
		const int type = 121;
		ItemDefinitions.SetMaxStack(type, 9999);
		List<bool> metadata = [];
		AppendBits(metadata, (uint)type, 14);
		AppendBits(metadata, 9, 8);
		metadata.Add(false);
		Append7BitEncodedInt(metadata, quotient);
		AppendBits(metadata, 1, NetCompression.GetBitSize(9999));
		metadata.Add(false);
		byte[] bytes = FrameStandaloneItem(metadata);
		Item result = NetCompression.ReceiveItem(new BinaryReader(new MemoryStream(bytes, writable: false)));
		True(result.IsFailure, "invalid overflow packet was accepted as an ordinary item");
	}

	private static void SevenBitRoundTrip(int value, byte sentinel) {
		byte[] bytes = Encode(writer => {
			writer.Write7BitEncodedInt(value);
			writer.Write(sentinel, 8);
		});
		ValueReader reader = Reader(bytes);
		Equal(value, reader.Read7BitEncodedInt(), "7-bit value");
		Equal(sentinel, reader.ReadByte(8), "7-bit sentinel");
	}

	private static void InvalidSevenBitRejected(byte[] bytes, byte sentinel) {
		ValueReader reader = Reader(bytes);
		Throws<FormatException>(() => reader.Read7BitEncodedInt());
		Equal(sentinel, reader.ReadByte(8), "malformed 7-bit sentinel");
	}

	private static void ItemMissingModPayloadDrained() {
		const int type = 131;
		ItemDefinitions.SetMaxStack(type, 1);
		ItemDefinitions.SetInitializer(type, _ => { });
		ValueReader reader = Reader(BuildCurrentItemPacket(type, [0xA1], [], 0xB2));
		Item result = NetCompression.ReceiveItem(reader, readStack: true, readFavorite: true);
		True(result.IsFailure, "missing ModItem payload was accepted");
		Equal((byte)0xB2, reader.ReadByte(8), "missing ModItem sentinel");
	}

	private static void ItemMissingModStillReadsGlobal() {
		const int type = 132;
		RecordingGlobalItem.Received.Clear();
		ItemDefinitions.SetMaxStack(type, 1);
		ItemDefinitions.SetInitializer(type, item => item.Globals.Add(new RecordingGlobalItem(0xC3)));
		ValueReader reader = Reader(BuildCurrentItemPacket(type, [0xA2], [[0xC3]], 0xD4));
		Item result = NetCompression.ReceiveItem(reader, readStack: true, readFavorite: true);
		True(result.IsFailure, "missing ModItem payload did not use failure isolation");
		SequenceEqual([0xC3], [.. RecordingGlobalItem.Received], "global callback after missing ModItem");
		Equal((byte)0xD4, reader.ReadByte(8), "missing ModItem with global sentinel");
	}

	private static void ItemThrowingModStillReadsGlobal() {
		const int type = 133;
		RecordingGlobalItem.Received.Clear();
		ItemDefinitions.SetMaxStack(type, 1);
		ItemDefinitions.SetInitializer(type, item => {
			item.ModItem = new ThrowingModItem();
			item.Globals.Add(new RecordingGlobalItem(0xE5));
		});
		ValueReader reader = Reader(BuildCurrentItemPacket(type, [0xA3], [[0xE5]], 0xF6));
		Item result = NetCompression.ReceiveItem(reader, readStack: true, readFavorite: true);
		True(result.IsFailure, "throwing ModItem did not use failure isolation");
		SequenceEqual([0xE5], [.. RecordingGlobalItem.Received], "global callback after throwing ModItem");
		Equal((byte)0xF6, reader.ReadByte(8), "throwing ModItem sentinel");
	}

	private static void ItemThrowingGlobalDoesNotSkipLaterGlobal() {
		const int type = 134;
		RecordingGlobalItem.Received.Clear();
		ItemDefinitions.SetMaxStack(type, 1);
		ItemDefinitions.SetInitializer(type, item => {
			item.Globals.Add(new RecordingGlobalItem(0x17, throws: true));
			item.Globals.Add(new RecordingGlobalItem(0x28));
		});
		ValueReader reader = Reader(BuildCurrentItemPacket(type, [], [[0x17], [0x28]], 0x39));
		Item result = NetCompression.ReceiveItem(reader, readStack: true, readFavorite: true);
		True(result.IsFailure, "throwing GlobalItem did not use failure isolation");
		SequenceEqual([0x17, 0x28], [.. RecordingGlobalItem.Received], "global callback order");
		Equal((byte)0x39, reader.ReadByte(8), "throwing GlobalItem sentinel");
	}

	private static void SendItemBinaryModFailureAtomic() {
		Item failed = SendingItem(201, int.MaxValue, maxStack: 2, mod: new SendingModItem(Enumerable.Repeat((byte)0xA1, 32).ToArray(), throws: true));
		using MemoryStream stream = new();
		BinaryWriter writer = new(stream);
		writer.Write(new byte[] { 0x31, 0x42, 0x53 });
		long start = stream.Position;

		Throws<InvalidDataException>(() => NetCompression.SendItem(failed, writer));
		Equal(start, stream.Length, "failed ModItem changed binary stream length");
		Equal(start, stream.Position, "failed ModItem changed binary stream position");

		Item expected = PlainItem(202, stack: 77, maxStack: 9999, prefix: 8, favorite: true);
		NetCompression.SendItem(expected, writer);
		stream.Position = start;
		AssertItem(expected, NetCompression.ReceiveItem(new BinaryReader(stream)), "binary ModItem recovery");
	}

	private static void SendItemBinaryGlobalFailureAtomic() {
		Item failed = SendingItem(203, int.MaxValue, maxStack: 2, globals: [new SendingGlobalItem(Enumerable.Repeat((byte)0xB2, 32).ToArray(), throws: true)]);
		using MemoryStream stream = new();
		BinaryWriter writer = new(stream);
		writer.Write(new byte[] { 0x64, 0x75 });
		long start = stream.Position;

		Throws<InvalidDataException>(() => NetCompression.SendItem(failed, writer));
		Equal(start, stream.Length, "failed GlobalItem changed binary stream length");
		Equal(start, stream.Position, "failed GlobalItem changed binary stream position");

		Item expected = PlainItem(204, stack: 19, maxStack: 250, prefix: 11, favorite: false);
		NetCompression.SendItem(expected, writer);
		stream.Position = start;
		AssertItem(expected, NetCompression.ReceiveItem(new BinaryReader(stream)), "binary GlobalItem recovery");
	}

	private static void SendItemValueWriterMisalignedReusable() {
		Item failed = SendingItem(205, 17, maxStack: 9999, mod: new SendingModItem([0xC3, 0xD4], throws: true));
		Item expected = PlainItem(206, stack: 321, maxStack: 9999, prefix: 27, favorite: true);

		byte[] bytes = Encode(writer => {
			writer.Write((byte)0b10101, 5);
			Throws<InvalidDataException>(() => NetCompression.SendItem(failed, writer, writeStack: true, writeFavorite: true));
			NetCompression.SendItem(expected, writer, writeStack: true, writeFavorite: true);
			writer.Write((byte)0b110101, 6);
		});

		ValueReader reader = Reader(bytes);
		Equal((byte)0b10101, reader.ReadByte(5), "misaligned prefix");
		AssertItem(expected, NetCompression.ReceiveItem(reader, readStack: true, readFavorite: true), "misaligned recovery item");
		Equal((byte)0b110101, reader.ReadByte(6), "misaligned recovery sentinel");
	}

	private static void SendItemInsideParentScopeReusable() {
		Item failed = SendingItem(207, 9, maxStack: 9999, globals: [new SendingGlobalItem([0xE5], throws: true)]);
		Item expected = PlainItem(208, stack: 444, maxStack: 9999, prefix: 31, favorite: true);

		byte[] bytes = Encode(writer => {
			using (writer.CreateScope(FrameTiers, optimizeForBytes: false)) {
				writer.Write((byte)0b101, 3);
				Throws<InvalidDataException>(() => NetCompression.SendItem(failed, writer, writeStack: true, writeFavorite: true));
				NetCompression.SendItem(expected, writer, writeStack: true, writeFavorite: true);
				writer.Write((byte)0b1101, 4);
			}
			writer.Write((byte)0xA6, 8);
		});

		ValueReader reader = Reader(bytes);
		using (reader.ReadScope(FrameTiers, optimizeForBytes: false)) {
			Equal((byte)0b101, reader.ReadByte(3), "parent prefix");
			AssertItem(expected, NetCompression.ReceiveItem(reader, readStack: true, readFavorite: true), "parent recovery item");
			Equal((byte)0b1101, reader.ReadByte(4), "parent tail");
		}
		Equal((byte)0xA6, reader.ReadByte(8), "parent sentinel");
	}

	private static void SendItemSuccessFormatCompatible() {
		Item item = PlainItem(209, stack: 25001, maxStack: 9999, prefix: 73, favorite: true);
		using MemoryStream stream = new();
		NetCompression.SendItem(item, new BinaryWriter(stream));
		byte[] expected = BuildRawItemPacket(item.type, item.stack, item.maxStack, item.prefix, item.favorited, writeStack: true);
		SequenceEqual(expected, stream.ToArray(), "successful item wire format");
	}

	private static void SendItemHooksCalledOnce() {
		SendingModItem mod = new([0x17, 0x28]);
		SendingGlobalItem first = new([0x39]);
		SendingGlobalItem second = new([0x4A, 0x5B]);
		Item item = SendingItem(210, 1, maxStack: 1, mod: mod, globals: [first, second]);

		using MemoryStream stream = new();
		NetCompression.SendItem(item, new BinaryWriter(stream));
		Equal(1, mod.Calls, "ModItem send count");
		Equal(1, first.Calls, "first GlobalItem send count");
		Equal(1, second.Calls, "second GlobalItem send count");
		True(stream.Length > 0, "successful hooks produced no packet");
	}

	private static void SendItemsBinaryMiddleFailureAtomic() {
		Item failed = SendingItem(212, 7, maxStack: 9999, mod: new SendingModItem([0x6C], throws: true));
		List<Item> rejected = [PlainItem(211, 3, 9999, 1, false), failed, PlainItem(213, 5, 9999, 2, true)];
		List<Item> expected = [PlainItem(214, 81, 9999, 3, true), PlainItem(215, 1, 1, 4, false)];

		using MemoryStream stream = new();
		BinaryWriter writer = new(stream);
		writer.Write((byte)0x7D);
		long start = stream.Position;
		Throws<InvalidDataException>(() => NetCompression.SendItems(rejected, writer));
		Equal(start, stream.Length, "failed item list changed binary stream length");
		Equal(start, stream.Position, "failed item list changed binary stream position");

		NetCompression.SendItems(expected, writer);
		stream.Position = start;
		AssertItems(expected, NetCompression.ReceiveItems(new BinaryReader(stream)), "binary list recovery");
	}

	private static void SendItemsValueWriterMiddleFailureAtomic() {
		Item failed = SendingItem(217, 4, maxStack: 9999, globals: [new SendingGlobalItem([0x8E], throws: true)]);
		List<Item> rejected = [PlainItem(216, 2, 9999, 5, false), failed];
		List<Item> expected = [PlainItem(218, 91, 250, 6, true), PlainItem(219, 1, 1, 7, false)];

		byte[] bytes = Encode(writer => {
			writer.Write((byte)0b110, 3);
			Throws<InvalidDataException>(() => NetCompression.SendItems(rejected, writer));
			NetCompression.SendItems(expected, writer);
			writer.Write((byte)0b10011, 5);
		});

		ValueReader reader = Reader(bytes);
		Equal((byte)0b110, reader.ReadByte(3), "list prefix");
		AssertItems(expected, NetCompression.ReceiveItems(reader), "value writer list recovery");
		Equal((byte)0b10011, reader.ReadByte(5), "list sentinel");
	}

	private static void SendItemsInsideParentScopeReusable() {
		Item failed = SendingItem(221, 6, maxStack: 9999, mod: new SendingModItem([0x9F], throws: true));
		List<Item> rejected = [PlainItem(220, 2, 9999, 8, false), failed];
		List<Item> expected = [PlainItem(222, 17, 250, 9, true)];

		byte[] bytes = Encode(writer => {
			using (writer.CreateScope(FrameTiers, optimizeForBytes: false)) {
				writer.Write((byte)0b11, 2);
				Throws<InvalidDataException>(() => NetCompression.SendItems(rejected, writer));
				NetCompression.SendItems(expected, writer);
				writer.Write((byte)0b101, 3);
			}
			writer.Write((byte)0xB0, 8);
		});

		ValueReader reader = Reader(bytes);
		using (reader.ReadScope(FrameTiers, optimizeForBytes: false)) {
			Equal((byte)0b11, reader.ReadByte(2), "nested list prefix");
			AssertItems(expected, NetCompression.ReceiveItems(reader), "nested list recovery");
			Equal((byte)0b101, reader.ReadByte(3), "nested list tail");
		}
		Equal((byte)0xB0, reader.ReadByte(8), "nested list sentinel");
	}

	private static void SendItemsGlobalAfterModFailureAtomic() {
		SendingModItem successfulMod = new([0xC1, 0xC2, 0xC3]);
		SendingGlobalItem failedGlobal = new([0xD1, 0xD2], throws: true);
		Item failed = SendingItem(224, 23, maxStack: 9999, mod: successfulMod, globals: [failedGlobal]);
		List<Item> rejected = [PlainItem(223, 1, 1, 0, false), failed];
		Item expected = PlainItem(225, 55, 9999, 10, true);

		byte[] bytes = Encode(writer => {
			writer.Write((byte)0b1, 1);
			Throws<InvalidDataException>(() => NetCompression.SendItems(rejected, writer));
			NetCompression.SendItem(expected, writer, writeStack: true, writeFavorite: true);
			writer.Write((byte)0xE3, 8);
		});

		Equal(1, successfulMod.Calls, "successful ModItem before failed global count");
		Equal(1, failedGlobal.Calls, "failed GlobalItem count");
		ValueReader reader = Reader(bytes);
		True(reader.ReadBoolean(), "global failure prefix");
		AssertItem(expected, NetCompression.ReceiveItem(reader, readStack: true, readFavorite: true), "global-after-mod recovery");
		Equal((byte)0xE3, reader.ReadByte(8), "global-after-mod sentinel");
	}

	private static void ScopeOutOfOrderNonEmptyRecoverable() {
		byte[] bytes = Encode(writer => {
			IDisposable outer = writer.CreateScope(FrameTiers, optimizeForBytes: false);
			writer.Write((byte)0b101, 3);
			IDisposable inner = writer.CreateScope(FrameTiers, optimizeForBytes: false);
			writer.Write((byte)0b11010, 5);
			Throws<InvalidOperationException>(outer.Dispose);
			inner.Dispose();
			writer.Write((byte)0b1110, 4);
			outer.Dispose();
			writer.Write((byte)0xF4, 8);
		});

		ValueReader reader = Reader(bytes);
		using (reader.ReadScope(FrameTiers, optimizeForBytes: false)) {
			Equal((byte)0b101, reader.ReadByte(3), "out-of-order outer prefix");
			using (reader.ReadScope(FrameTiers, optimizeForBytes: false))
				Equal((byte)0b11010, reader.ReadByte(5), "out-of-order inner payload");
			Equal((byte)0b1110, reader.ReadByte(4), "out-of-order outer tail");
		}
		Equal((byte)0xF4, reader.ReadByte(8), "out-of-order sentinel");
	}

	private static void ScopeOutOfOrderEmptyRecoverable() {
		byte[] bytes = Encode(writer => {
			IDisposable outer = writer.CreateScope(FrameTiers, optimizeForBytes: false);
			writer.Write((byte)0b10, 2);
			IDisposable inner = writer.CreateScope(FrameTiers, optimizeForBytes: true);
			Throws<InvalidOperationException>(outer.Dispose);
			inner.Dispose();
			writer.Write((byte)0b10101, 5);
			outer.Dispose();
			writer.Write((byte)0x85, 8);
		});

		ValueReader reader = Reader(bytes);
		using (reader.ReadScope(FrameTiers, optimizeForBytes: false)) {
			Equal((byte)0b10, reader.ReadByte(2), "empty recovery prefix");
			using (reader.ReadScope(FrameTiers, optimizeForBytes: true)) { }
			Equal((byte)0b10101, reader.ReadByte(5), "empty recovery tail");
		}
		Equal((byte)0x85, reader.ReadByte(8), "empty recovery sentinel");
	}

	private static void ScopeOutOfOrderThreeLevelRecoverable() {
		byte[] bytes = Encode(writer => {
			IDisposable outer = writer.CreateScope(FrameTiers, optimizeForBytes: false);
			writer.Write(true);
			IDisposable middle = writer.CreateScope(FrameTiers, optimizeForBytes: false);
			writer.Write((byte)0b11, 2);
			IDisposable inner = writer.CreateScope(FrameTiers, optimizeForBytes: true);
			writer.Write((byte)0xA7, 8);
			Throws<InvalidOperationException>(outer.Dispose);
			Throws<InvalidOperationException>(middle.Dispose);
			inner.Dispose();
			writer.Write((byte)0b101, 3);
			middle.Dispose();
			writer.Write((byte)0b1101, 4);
			outer.Dispose();
		});

		ValueReader reader = Reader(bytes);
		using (reader.ReadScope(FrameTiers, optimizeForBytes: false)) {
			True(reader.ReadBoolean(), "three-level outer prefix");
			using (reader.ReadScope(FrameTiers, optimizeForBytes: false)) {
				Equal((byte)0b11, reader.ReadByte(2), "three-level middle prefix");
				using (reader.ReadScope(FrameTiers, optimizeForBytes: true))
					Equal((byte)0xA7, reader.ReadByte(8), "three-level inner payload");
				Equal((byte)0b101, reader.ReadByte(3), "three-level middle tail");
			}
			Equal((byte)0b1101, reader.ReadByte(4), "three-level outer tail");
		}
	}

	private static void ScopeDoubleCloseStillRejected() {
		using MemoryStream stream = new();
		ValueWriter writer = new(stream);
		IDisposable scope = writer.CreateScope(FrameTiers, optimizeForBytes: false);
		writer.Write((byte)0b1011, 4);
		scope.Dispose();
		Throws<ObjectDisposedException>(scope.Dispose);
		writer.Write((byte)0x96, 8);
		writer.Flush();

		ValueReader reader = Reader(stream.ToArray());
		using (reader.ReadScope(FrameTiers, optimizeForBytes: false))
			Equal((byte)0b1011, reader.ReadByte(4), "double-close payload");
		Equal((byte)0x96, reader.ReadByte(8), "double-close sentinel");
	}

	private static Item PlainItem(int type, int stack, int maxStack, int prefix, bool favorite) {
		ItemDefinitions.SetMaxStack(type, maxStack);
		return new Item(type, stack, prefix) { favorited = favorite };
	}

	private static Item SendingItem(int type, int stack, int maxStack, SendingModItem mod = null, SendingGlobalItem[] globals = null) {
		Item item = PlainItem(type, stack, maxStack, prefix: 0, favorite: false);
		item.ModItem = mod;
		if (globals is not null)
			item.Globals.AddRange(globals);
		return item;
	}

	private static void AssertItem(Item expected, Item actual, string label) {
		False(actual.IsFailure, label + " became failure item");
		Equal(expected.type, actual.type, label + " type");
		Equal(expected.stack, actual.stack, label + " stack");
		Equal(expected.prefix, actual.prefix, label + " prefix");
		Equal(expected.favorited, actual.favorited, label + " favorite");
	}

	private static void AssertItems(List<Item> expected, List<Item> actual, string label) {
		Equal(expected.Count, actual.Count, label + " count");
		for (int i = 0; i < expected.Count; i++)
			AssertItem(expected[i], actual[i], $"{label} item {i}");
	}

	private static byte[] BuildCurrentItemPacket(int type, byte[] modPayload, byte[][] globalPayloads, byte sentinel) {
		return Encode(writer => {
			using (writer.CreateScope(NetCompression.lengthTiers, optimizeForBytes: false)) {
				writer.Write(type, ModContent.GetInstance<ItemTypeTracker>().BitCount);
				writer.Write((uint)0, ModContent.GetInstance<ItemPrefixTracker>().BitCount - 1);
				writer.Write(false);
			}

			if (modPayload.Length > 0) {
				writer.Write(true);
				using (writer.CreateScope(NetCompression.lengthTiers, optimizeForBytes: true))
					writer.WriteContents(modPayload);
			} else {
				writer.Write(false);
			}

			if (globalPayloads.Length > 0) {
				writer.Write(true);
				NetCompression.lengthTiers.WriteTo(writer, (uint)globalPayloads.Length);
				foreach (byte[] payload in globalPayloads) {
					using (writer.CreateScope(NetCompression.lengthTiers, optimizeForBytes: true))
						writer.WriteContents(payload);
				}
			} else {
				writer.Write(false);
			}

			writer.Write(sentinel, 8);
		});
	}

	private static byte[] BuildRawItemPacket(int type, int stack, int maxStack, int prefix, bool favorite, bool writeStack) {
		List<bool> metadata = [];
		AppendBits(metadata, (uint)type, 14);
		AppendBits(metadata, (uint)prefix, 8);
		if (writeStack && maxStack > 1) {
			bool partialOrFull = stack <= maxStack;
			metadata.Add(partialOrFull);
			int encodedStack = stack;
			if (!partialOrFull) {
				Append7BitEncodedInt(metadata, stack / maxStack);
				encodedStack = stack % maxStack;
			}
			AppendBits(metadata, (uint)encodedStack, NetCompression.GetBitSize(maxStack));
		}
		metadata.Add(favorite);
		return FrameStandaloneItem(metadata);
	}

	private static byte[] FrameStandaloneItem(List<bool> metadata) {
		List<bool> bits = [];
		bits.Add(true);
		AppendLength(bits, (uint)metadata.Count);
		bits.AddRange(metadata);
		bits.Add(false);
		bits.Add(false);
		return ToBytes(bits);
	}

	private static void AppendLength(List<bool> bits, uint value) {
		if (value <= 15) {
			AppendBits(bits, 0b00, 2);
			AppendBits(bits, value, 5);
		} else if (value <= 79) {
			AppendBits(bits, 0b01, 2);
			AppendBits(bits, value - 16, 7);
		} else if (value <= 335) {
			AppendBits(bits, 0b10, 2);
			AppendBits(bits, value - 80, 9);
		} else if (value <= 4431) {
			AppendBits(bits, 0b11, 2);
			AppendBits(bits, value - 336, 13);
		} else if (value <= 135503) {
			AppendBits(bits, 0b011, 3);
			AppendBits(bits, value - 4432, 18);
		} else {
			AppendBits(bits, 0b111, 3);
			AppendBits(bits, value - 135504, 32);
		}
	}

	private static void Append7BitEncodedInt(List<bool> bits, int value) {
		uint remaining = (uint)value;
		do {
			uint chunk = remaining & 0x7F;
			remaining >>= 7;
			AppendBits(bits, chunk, 7);
			bits.Add(remaining != 0);
		} while (remaining != 0);
	}

	private static void AppendBits(List<bool> bits, ulong value, int count) {
		for (int i = 0; i < count; i++)
			bits.Add(((value >> i) & 1UL) != 0);
	}

	private static byte[] ToBytes(List<bool> bits) {
		byte[] bytes = new byte[(bits.Count + 7) / 8];
		for (int i = 0; i < bits.Count; i++) {
			if (bits[i])
				bytes[i >> 3] |= (byte)(1 << (i & 7));
		}
		return bytes;
	}

	private static byte[] PackBits(params (ulong value, int count)[] fields) {
		List<bool> bits = [];
		foreach ((ulong value, int count) in fields)
			AppendBits(bits, value, count);
		return ToBytes(bits);
	}

	private static uint Mask32(int bits) => bits == 32 ? uint.MaxValue : (1u << bits) - 1;

	private static void Equal<T>(T expected, T actual, string label) where T : notnull {
		if (!EqualityComparer<T>.Default.Equals(expected, actual))
			throw new CheckFailedException($"{label}: expected {expected}, got {actual}");
	}

	private static void SequenceEqual(byte[] expected, byte[] actual, string label) {
		if (!expected.AsSpan().SequenceEqual(actual))
			throw new CheckFailedException($"{label}: expected {Convert.ToHexString(expected)}, got {Convert.ToHexString(actual)}");
	}

	private static void True(bool value, string label) {
		if (!value)
			throw new CheckFailedException(label + ": expected true");
	}

	private static void False(bool value, string label) {
		if (value)
			throw new CheckFailedException(label + ": expected false");
	}

	private static void Throws<T>(Action action) where T : Exception {
		try {
			action();
		} catch (T) {
			return;
		}
		throw new CheckFailedException($"expected {typeof(T).Name}");
	}
}
