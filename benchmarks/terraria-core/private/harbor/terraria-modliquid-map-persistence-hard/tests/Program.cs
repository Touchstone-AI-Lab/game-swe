using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Microsoft.Xna.Framework;
using ModLiquidLib.Hooks;
using ModLiquidLib.IO;
using ModLiquidLib.ModLoader;
using MonoMod.Cil;
using Terraria.Map;
using Terraria.Localization;
using Terraria.ModLoader;
using Terraria.Social;
using Terraria.Utilities;

internal static class ContractProgram
{
    private static readonly Dictionary<string, Action> Cases = new()
    {
        ["empty_map_writes_no_header"] = EmptyMapWritesNothing,
        ["hidden_mod_entries_do_not_create_sidecar"] = HiddenEntriesIgnored,
        ["header_types_are_unique_and_ascending"] = HeaderUniqueAscending,
        ["visible_threshold_is_strictly_above_eighteen"] = VisibleThreshold,
        ["unrepresentable_header_count_is_rejected"] = HeaderCountOverflow,
        ["tile_header_preserves_identity_and_option"] = TileHeader,
        ["liquid_header_preserves_identity_and_option"] = LiquidHeader,
        ["wall_header_preserves_identity_and_option"] = WallHeader,
        ["unknown_header_entry_uses_missing_sentinel"] = UnknownHeader,
        ["tile_option_out_of_range_falls_back_to_zero"] = TileOptionFallback,
        ["liquid_option_out_of_range_falls_back_to_zero"] = LiquidOptionFallback,
        ["wall_option_out_of_range_falls_back_to_zero"] = WallOptionFallback,
        ["duplicate_old_type_is_rejected"] = DuplicateHeaderRejected,
        ["header_discriminator_must_be_boolean"] = InvalidHeaderDiscriminator,
        ["header_old_types_must_be_strictly_ascending"] = UnsortedHeaderRejected,
        ["header_rejects_vanilla_old_type"] = VanillaHeaderTypeRejected,
        ["zero_entry_header_rejects_payload"] = ZeroHeaderRejectsPayload,
        ["malformed_header_string_is_invaliddata"] = MalformedHeaderString,
        ["sparse_stream_preserves_first_cell"] = SparseFirstCell,
        ["sparse_stream_preserves_interior_cell"] = SparseInteriorCell,
        ["sparse_stream_crosses_column_boundary"] = SparseColumnBoundary,
        ["sparse_skip_splits_at_255"] = SparseSkip255,
        ["sparse_stream_preserves_final_cell"] = SparseFinalCell,
        ["trailing_skip_does_not_invent_record"] = TrailingSkip,
        ["sparse_skip_past_world_is_rejected"] = SparseSkipPastWorld,
        ["rle_uses_one_byte_at_255"] = RleByteBoundary,
        ["rle_uses_two_bytes_at_256"] = RleUshortStart,
        ["rle_uses_two_bytes_at_65535"] = RleUshortBoundary,
        ["rle_uses_four_bytes_at_65536"] = RleUintStart,
        ["rle_preserves_light_and_color"] = RleLightColor,
        ["adjacent_distinct_records_use_continuation"] = AdjacentContinuation,
        ["rle_crosses_column_boundary_in_scan_order"] = RleColumnBoundary,
        ["run_past_world_end_is_rejected"] = RunPastEnd,
        ["continuation_at_world_end_is_rejected"] = ContinuationPastEnd,
        ["noncanonical_run_width_is_rejected"] = NonCanonicalRun,
        ["reserved_tile_flags_are_rejected_transactionally"] = ReservedFlagsRollback,
        ["missing_type_table_reference_is_rejected"] = MissingTypeReference,
        ["null_type_table_is_rejected"] = NullTypeTable,
        ["truncated_tile_record_is_rejected"] = TruncatedTile,
        ["zero_rle_count_is_rejected"] = ZeroRunRejected,
        ["run_width_without_rle_is_rejected"] = WidthWithoutRunRejected,
        ["uint_run_requires_ushort_width_flag"] = UintRunRequiresUshortFlag,
        ["malformed_second_record_rolls_back_first"] = PrefixRollback,
        ["trailing_bytes_roll_back_payload"] = TrailingBytesRollback,
        ["valid_payload_commits_each_decoded_cell_once"] = CommitOnce,
        ["missing_content_maps_to_type_zero"] = MissingContentMapsZero,
        ["skipped_vanilla_cells_remain_untouched"] = SkippedCellsUntouched,
        ["file_write_uses_tlmap_extension"] = FileWriteExtension,
        ["local_empty_write_deletes_local_sidecar"] = LocalDelete,
        ["cloud_empty_write_deletes_cloud_sidecar"] = CloudDelete,
        ["missing_cloud_provider_never_deletes_local_file"] = MissingCloudNoLocalDelete,
        ["missing_read_target_performs_no_read"] = MissingReadNoRead,
        ["file_read_uses_tlmap_and_applies_valid_payload"] = FileReadApplies,
        ["malformed_file_read_rolls_back_map"] = MalformedFileRollback,
        ["writer_failure_preserves_existing_stream"] = WriterFailurePreservesStream,
        ["writer_uses_one_map_snapshot"] = WriterUsesOneMapSnapshot,
        ["writer_rejects_ambiguous_registry_membership"] = WriterRejectsAmbiguousRegistry,
        ["writer_rejects_lookup_below_mod_range"] = WriterRejectsLookupBelowRange,
        ["writer_rejects_unrepresentable_option"] = WriterRejectsUnrepresentableOption,
        ["file_write_preparation_failure_performs_no_io"] = FileWriteFailurePerformsNoIo,
        ["nontile_identity_ambiguity_is_rejected"] = NontileIdentityAmbiguity,
        ["resolved_lookup_below_mod_range_is_rejected"] = ResolvedLookupBelowRange,
        ["resolved_lookup_overflow_is_rejected"] = ResolvedLookupOverflow,
        ["resolved_content_requires_an_option"] = ResolvedContentRequiresOption,
        ["world_swap_during_resolution_is_rejected"] = WorldSwapDuringResolution,
        ["dimension_change_during_resolution_is_rejected"] = DimensionChangeDuringResolution,
        ["commit_failure_rolls_back_written_prefix"] = CommitFailureRollsBack,
        ["file_commit_failure_rolls_back_written_prefix"] = FileCommitFailureRollsBack,
        ["save_hook_forwards_unique_anchor"] = SaveHookForwardsUniqueAnchor,
        ["save_hook_rejects_missing_anchor"] = SaveHookRejectsMissingAnchor,
        ["save_hook_rejects_duplicate_anchor"] = SaveHookRejectsDuplicateAnchor,
        ["load_hook_forwards_unique_anchor"] = LoadHookForwardsUniqueAnchor,
        ["load_hook_rejects_missing_anchor"] = LoadHookRejectsMissingAnchor,
        ["load_hook_rejects_duplicate_anchor"] = LoadHookRejectsDuplicateAnchor,
        ["registry_publication_is_atomic_deterministic_and_coherent"] = RegistryPublicationIsAtomicDeterministicAndCoherent,
        ["registry_rejects_out_of_range_type_without_mutation"] = RegistryRejectsOutOfRangeTypeWithoutMutation,
        ["registry_rejects_map_type_collision_without_mutation"] = RegistryRejectsMapTypeCollisionWithoutMutation,
        ["registry_rejects_ushort_overflow_without_mutation"] = RegistryRejectsUshortOverflowWithoutMutation,
        ["registry_rejects_null_localized_name_without_mutation"] = RegistryRejectsNullLocalizedNameWithoutMutation,
        ["registry_rejects_null_name_callback_without_mutation"] = RegistryRejectsNullNameCallbackWithoutMutation,
        ["client_unload_clears_all_published_state"] = ClientUnloadClearsAllPublishedState,
        ["dedicated_server_unload_clears_all_published_state"] = DedicatedServerUnloadClearsAllPublishedState,
        ["map_option_resolves_from_published_base_once"] = MapOptionResolvesFromPublishedBaseOnce,
        ["invalid_map_option_preserves_input"] = InvalidMapOptionPreservesInput,
        ["map_option_rejects_generation_change"] = MapOptionRejectsGenerationChange,
        ["map_option_rejects_loader_generation_change_before_callback"] = MapOptionRejectsLoaderGenerationChangeBeforeCallback,
        ["map_option_rejects_direct_topology_change"] = MapOptionRejectsDirectTopologyChange,
        ["map_option_rejects_owner_alias_outside_range"] = MapOptionRejectsOwnerAliasOutsideRange,
        ["writer_rejects_registry_republication_before_output"] = WriterRejectsRegistryRepublicationBeforeOutput,
        ["reader_rejects_registry_republication_before_commit"] = ReaderRejectsRegistryRepublicationBeforeCommit,
        ["file_writer_republication_failure_performs_no_io"] = FileWriterRepublicationFailurePerformsNoIo,
        ["file_reader_republication_failure_preserves_map"] = FileReaderRepublicationFailurePreservesMap,
        ["finish_setup_hook_forwards_unique_anchor"] = FinishSetupHookForwardsUniqueAnchor,
        ["finish_setup_hook_rejects_missing_anchor"] = FinishSetupHookRejectsMissingAnchor,
        ["finish_setup_hook_rejects_duplicate_anchor"] = FinishSetupHookRejectsDuplicateAnchor,
        ["liquid_lookup_hook_forwards_both_unique_anchors"] = LiquidLookupHookForwardsBothUniqueAnchors,
        ["liquid_lookup_hook_rejects_missing_second_anchor"] = LiquidLookupHookRejectsMissingSecondAnchor,
        ["liquid_lookup_hook_rejects_duplicate_first_anchor"] = LiquidLookupHookRejectsDuplicateFirstAnchor,
        ["liquid_lookup_hook_rejects_reversed_anchors"] = LiquidLookupHookRejectsReversedAnchors,
        ["liquid_count_hook_forwards_all_unique_anchors"] = LiquidCountHookForwardsAllUniqueAnchors,
        ["liquid_count_hook_rejects_missing_third_anchor"] = LiquidCountHookRejectsMissingThirdAnchor,
        ["liquid_count_hook_rejects_duplicate_middle_anchor"] = LiquidCountHookRejectsDuplicateMiddleAnchor,
        ["liquid_count_hook_rejects_reversed_anchors"] = LiquidCountHookRejectsReversedAnchors,
    };

    public static int Main(string[] args)
    {
        if (args.Length != 1 || !Cases.TryGetValue(args[0], out Action test)) return 2;
        try { TestHooks.Reset(); test(); Console.WriteLine("PASS"); return 0; }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }

    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static void Set(int x, int y, ushort type, byte light = 255, byte color = 0)
        => Terraria.Main.Map[x, y] = MapTile.Create(type, light, color);

    private static byte[] WriteMap(out bool hasData)
    {
        using var stream = new MemoryStream();
        using var writer = new BinaryWriter(stream);
        hasData = MapLiquidIO.WriteModMap(writer); writer.Flush(); return stream.ToArray();
    }

    private static byte[] WriteData()
    {
        using var stream = new MemoryStream(); using var writer = new BinaryWriter(stream);
        MapLiquidIO.WriteMapData(writer); writer.Flush(); return stream.ToArray();
    }

    private static void ReadData(byte[] bytes, IDictionary<ushort, ushort> table)
    {
        using var reader = new BinaryReader(new MemoryStream(bytes));
        MapLiquidIO.ReadMapData(reader, table);
    }

    private static byte[] FullFrame(IEnumerable<(ushort oldType, bool tile, string mod, string name, ushort option)> entries, byte[] payload)
    {
        var list = entries.ToList(); using var stream = new MemoryStream(); using var writer = new BinaryWriter(stream);
        writer.Write((ushort)list.Count);
        foreach (var e in list) { writer.Write(e.oldType); writer.Write(e.tile); writer.Write(e.mod); writer.Write(e.name); writer.Write(e.option); }
        writer.Write(payload); writer.Flush(); return stream.ToArray();
    }

    private static byte[] OneRecord(ushort oldType, byte flags = 0, byte light = 255, byte color = 0, uint? run = null)
    {
        using var stream = new MemoryStream(); using var writer = new BinaryWriter(stream);
        writer.Write(flags); writer.Write(oldType);
        if ((flags & 1) != 0) writer.Write(light);
        if ((flags & 2) != 0) writer.Write(color);
        if ((flags & 4) != 0)
        {
            uint value = run ?? 1;
            if ((flags & 0x10) != 0) writer.Write(value);
            else if ((flags & 8) != 0) writer.Write((ushort)value);
            else writer.Write((byte)value);
        }
        writer.Flush(); return stream.ToArray();
    }

    private static ModTile RegisterTile(ushort mapType, int tileType = 7, string name = "Tile", int lookup = 1200, int options = 4)
    {
        var tile = new ModTile { Type = checked((ushort)tileType), Name = name, Mod = new Mod { Name = "Example" } };
        MapLoader.entryToTile[mapType] = checked((ushort)tileType); TileLoader.Tiles[tileType] = tile; MapHelper.tileLookup[tileType] = lookup;
        MapLoader.tileEntries[tile.Type] = Enumerable.Range(0, options).Select(_ => new object()).ToList();
        ModContent.Register("Example", name, tile); return tile;
    }

    private static ModLiquid RegisterLiquid(ushort mapType, int liquidType = 8, string name = "Liquid", int lookup = 1300, int options = 4)
    {
        var liquid = new ModLiquid { Type = (ushort)liquidType, Name = name, Mod = new Mod { Name = "Example" } };
        LiquidLoader.LiquidCount = Math.Max(LiquidLoader.LiquidCount, liquidType + 1);
        Array.Resize(ref MapLiquidLoader.liquidLookup, LiquidLoader.LiquidCount);
        var entries = new List<MapEntry>();
        for (int option = 0; option < options; option++)
        {
            entries.Add(new MapEntry(new Color(option), new LocalizedText(name + option)));
            MapLiquidLoader.entryToLiquid[checked((ushort)(lookup + option))] = checked((ushort)liquidType);
        }
        MapLiquidLoader.entryToLiquid[mapType] = checked((ushort)liquidType);
        MapLiquidLoader.liquidEntries[checked((ushort)liquidType)] = entries;
        LiquidLoader.Liquids[liquidType] = liquid; MapLiquidLoader.liquidLookup[liquidType] = checked((ushort)lookup);
        ModContent.Register("Example", name, liquid); return liquid;
    }

    private static ModWall RegisterWall(ushort mapType, int wallType = 9, string name = "Wall", int lookup = 1400, int options = 4)
    {
        var wall = new ModWall { Type = checked((ushort)wallType), Name = name, Mod = new Mod { Name = "Example" } };
        MapLoader.entryToWall[mapType] = checked((ushort)wallType); WallLoader.Walls[wallType] = wall; MapHelper.wallLookup[wallType] = lookup;
        MapLoader.wallEntries[wall.Type] = Enumerable.Range(0, options).Select(_ => new object()).ToList();
        ModContent.Register("Example", name, wall); return wall;
    }

    private static void EmptyMapWritesNothing()
    {
        byte[] bytes = WriteMap(out bool has); Check(!has && bytes.Length == 0, "empty map emitted a header");
    }

    private static void HiddenEntriesIgnored()
    {
        Set(0, 0, 1100, 18); RegisterTile(1100, lookup: 1100);
        byte[] bytes = WriteMap(out bool has); Check(!has && bytes.Length == 0, "hidden map entry created a sidecar");
    }

    private static void HeaderUniqueAscending()
    {
        Set(0, 0, 1200); Set(0, 1, 1100); Set(0, 2, 1200);
        byte[] bytes = WriteMap(out bool has); using var r = new BinaryReader(new MemoryStream(bytes));
        Check(has && r.ReadUInt16() == 2, "header count");
        ushort first = r.ReadUInt16(); r.ReadBoolean(); r.ReadString(); r.ReadString(); r.ReadUInt16();
        ushort second = r.ReadUInt16(); Check(first == 1100 && second == 1200, "types are not unique/ascending");
    }

    private static void VisibleThreshold()
    {
        Set(0, 0, 1100, 18); Set(0, 1, 1200, 19);
        byte[] bytes = WriteMap(out bool has); using var r = new BinaryReader(new MemoryStream(bytes));
        Check(has && r.ReadUInt16() == 1 && r.ReadUInt16() == 1200, "visibility threshold mismatch");
    }

    private static void HeaderCountOverflow()
    {
        TestHooks.Reset(1, ushort.MaxValue + 1); MapHelper.modPosition = 0;
        for (int y = 0; y <= ushort.MaxValue; y++) Set(0, y, (ushort)y);
        using var stream = new MemoryStream(); using var writer = new BinaryWriter(stream);
        Expect<InvalidDataException>(() => MapLiquidIO.WriteModMap(writer));
        Check(stream.Length == 0, "overflow emitted partial header");
    }

    private static (ushort type, bool tile, string mod, string name, ushort option) HeaderEntry(ushort mapType)
    {
        Set(0, 0, mapType); byte[] bytes = WriteMap(out bool has); Check(has, "no map");
        using var r = new BinaryReader(new MemoryStream(bytes)); Check(r.ReadUInt16() == 1, "entry count");
        return (r.ReadUInt16(), r.ReadBoolean(), r.ReadString(), r.ReadString(), r.ReadUInt16());
    }

    private static void TileHeader()
    {
        RegisterTile(1203, lookup: 1200); var e = HeaderEntry(1203);
        Check(e == (1203, true, "Example", "Tile", 3), "tile header mismatch");
    }

    private static void LiquidHeader()
    {
        RegisterLiquid(1302, lookup: 1300); var e = HeaderEntry(1302);
        Check(e == (1302, false, "Example", "Liquid", 2), "liquid header mismatch");
    }

    private static void WallHeader()
    {
        RegisterWall(1401, lookup: 1400); var e = HeaderEntry(1401);
        Check(e == (1401, false, "Example", "Wall", 1), "wall header mismatch");
    }

    private static void UnknownHeader()
    {
        var e = HeaderEntry(1600); Check(e == (1600, true, "", "", 0), "missing sentinel mismatch");
    }

    private static void ReadFull(byte[] frame)
    {
        using var r = new BinaryReader(new MemoryStream(frame)); MapLiquidIO.ReadModMap(r);
    }

    private static void TileOptionFallback()
    {
        TestHooks.Reset(1, 1);
        RegisterTile(1200, lookup: 1500, options: 2); ReadFull(FullFrame(new[] { ((ushort)1200, true, "Example", "Tile", (ushort)9) }, new byte[] { 0 }.Concat(OneRecord(1200)).ToArray()));
        Check(Terraria.Main.Map[0, 0].Type == 1500, "tile option did not fall back");
    }

    private static void LiquidOptionFallback()
    {
        TestHooks.Reset(1, 1);
        RegisterLiquid(1300, lookup: 1600, options: 2); ReadFull(FullFrame(new[] { ((ushort)1300, false, "Example", "Liquid", (ushort)9) }, new byte[] { 0 }.Concat(OneRecord(1300)).ToArray()));
        Check(Terraria.Main.Map[0, 0].Type == 1600, "liquid option did not fall back");
    }

    private static void WallOptionFallback()
    {
        TestHooks.Reset(1, 1);
        RegisterWall(1400, lookup: 1700, options: 2); ReadFull(FullFrame(new[] { ((ushort)1400, false, "Example", "Wall", (ushort)9) }, new byte[] { 0 }.Concat(OneRecord(1400)).ToArray()));
        Check(Terraria.Main.Map[0, 0].Type == 1700, "wall option did not fall back");
    }

    private static void DuplicateHeaderRejected()
    {
        Set(0, 0, 77); MapTile[] before = Terraria.Main.Map.Snapshot();
        byte[] frame = FullFrame(new[] { ((ushort)1200,true,"","",(ushort)0), ((ushort)1200,true,"","",(ushort)0) }, Array.Empty<byte>());
        Expect<InvalidDataException>(() => ReadFull(frame)); Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()), "duplicate header mutated map");
    }

    private static void InvalidHeaderDiscriminator()
    {
        TestHooks.Reset(1, 1);
        using var stream = new MemoryStream(); using var writer = new BinaryWriter(stream);
        writer.Write((ushort)1); writer.Write((ushort)1000); writer.Write((byte)2);
        writer.Write(""); writer.Write(""); writer.Write((ushort)0); writer.Write((byte)0); writer.Write(OneRecord(1000));
        writer.Flush(); MapTile[] before = Terraria.Main.Map.Snapshot();
        Expect<InvalidDataException>(() => ReadFull(stream.ToArray()));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()) && Terraria.Main.Map.SetCalls == 0, "invalid discriminator mutated map");
    }

    private static void UnsortedHeaderRejected()
    {
        TestHooks.Reset(1, 1); MapTile[] before = Terraria.Main.Map.Snapshot();
        byte[] frame = FullFrame(new[] { ((ushort)1100,true,"","",(ushort)0), ((ushort)1000,true,"","",(ushort)0) }, new byte[] { 0 }.Concat(OneRecord(1000)).ToArray());
        Expect<InvalidDataException>(() => ReadFull(frame));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()) && Terraria.Main.Map.SetCalls == 0, "unsorted header mutated map");
    }

    private static void VanillaHeaderTypeRejected()
    {
        TestHooks.Reset(1, 1); MapTile[] before = Terraria.Main.Map.Snapshot();
        byte[] frame = FullFrame(new[] { ((ushort)999,true,"","",(ushort)0) }, new byte[] { 0 }.Concat(OneRecord(999)).ToArray());
        Expect<InvalidDataException>(() => ReadFull(frame));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()) && Terraria.Main.Map.SetCalls == 0, "vanilla header type mutated map");
    }

    private static void ZeroHeaderRejectsPayload()
    {
        TestHooks.Reset(1, 1); MapTile[] before = Terraria.Main.Map.Snapshot();
        Expect<InvalidDataException>(() => ReadFull(new byte[] { 0, 0, 1 }));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()) && Terraria.Main.Map.SetCalls == 0, "zero-entry payload mutated map");
    }

    private static void MalformedHeaderString()
    {
        TestHooks.Reset(1, 1); MapTile[] before = Terraria.Main.Map.Snapshot();
        byte[] frame = { 1, 0, 0xE8, 0x03, 1, 0xFF, 0xFF, 0xFF, 0xFF, 0x10 };
        Expect<InvalidDataException>(() => ReadFull(frame));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()) && Terraria.Main.Map.SetCalls == 0, "malformed header mutated map");
    }

    private static void RoundtripAt(int width, int height, int x, int y)
    {
        TestHooks.Reset(width, height); Set(x, y, 1100, 200, 4); byte[] data = WriteData();
        Terraria.Main.Map = new MapStorage(width, height); ReadData(data, new Dictionary<ushort, ushort> { [1100] = 2100 });
        MapTile tile = Terraria.Main.Map[x, y]; Check(tile.Type == 2100 && tile.Light == 200 && tile.Color == 4, "roundtrip target mismatch");
    }

    private static void SparseFirstCell() => RoundtripAt(3, 3, 0, 0);
    private static void SparseInteriorCell() => RoundtripAt(3, 3, 1, 1);
    private static void SparseColumnBoundary() => RoundtripAt(3, 3, 1, 0);

    private static void SparseSkip255()
    {
        TestHooks.Reset(1, 257); Set(0, 255, 1100); byte[] data = WriteData();
        Check(data[0] == 255 && data[1] == 0, "skip was not split at 255");
        Terraria.Main.Map = new MapStorage(1, 257); ReadData(data, new Dictionary<ushort, ushort> { [1100] = 2100 });
        Check(Terraria.Main.Map[0, 255].Type == 2100, "split skip decoded at wrong cell");
    }

    private static void SparseFinalCell() => RoundtripAt(3, 3, 2, 2);

    private static void TrailingSkip()
    {
        TestHooks.Reset(1, 5); Set(0, 1, 1100); byte[] data = WriteData();
        Terraria.Main.Map = new MapStorage(1, 5); Set(0, 4, 77); ReadData(data, new Dictionary<ushort, ushort> { [1100] = 2100 });
        Check(Terraria.Main.Map[0, 1].Type == 2100 && Terraria.Main.Map[0, 4].Type == 77, "trailing skip invented/overwrote record");
    }

    private static void SparseSkipPastWorld()
        => UnchangedAfterInvalid(new byte[] { 5 }, new Dictionary<ushort, ushort>(), 1, 2);

    private static byte[] RunBytes(uint repeats)
    {
        TestHooks.Reset(1, checked((int)repeats + 1)); for (int y = 0; y <= repeats; y++) Set(0, y, 1100);
        int i = 0, j = 0; bool next = false; using var s = new MemoryStream(); using var w = new BinaryWriter(s);
        MapLiquidIO.WriteMapTile(ref i, ref j, w, ref next); w.Flush(); return s.ToArray();
    }

    private static void RleByteBoundary()
    {
        byte[] b = RunBytes(255); Check((b[0] & 0x1C) == 4 && b.Length == 4 && b[3] == 255, "255 run width");
    }
    private static void RleUshortStart()
    {
        byte[] b = RunBytes(256); Check((b[0] & 0x1C) == 12 && b.Length == 5 && BitConverter.ToUInt16(b, 3) == 256, "256 run width");
    }
    private static void RleUshortBoundary()
    {
        byte[] b = RunBytes(65535); Check((b[0] & 0x1C) == 12 && b.Length == 5 && BitConverter.ToUInt16(b, 3) == 65535, "65535 run width");
    }
    private static void RleUintStart()
    {
        byte[] b = RunBytes(65536); Check((b[0] & 0x1C) == 28 && b.Length == 7 && BitConverter.ToUInt32(b, 3) == 65536, "65536 run width");
    }

    private static void RleLightColor()
    {
        TestHooks.Reset(1, 4); for (int y = 0; y < 4; y++) Set(0, y, 1100, 77, 9); byte[] data = WriteData();
        Terraria.Main.Map = new MapStorage(1, 4); ReadData(data, new Dictionary<ushort, ushort> { [1100] = 2200 });
        Check(Enumerable.Range(0,4).All(y => Terraria.Main.Map[0,y].Type == 2200 && Terraria.Main.Map[0,y].Light == 77 && Terraria.Main.Map[0,y].Color == 9), "RLE fields lost");
    }

    private static void AdjacentContinuation()
    {
        TestHooks.Reset(1, 2); Set(0,0,1100); Set(0,1,1200); byte[] data = WriteData();
        Check(data[0] == 0 && (data[1] & 0x20) != 0, "continuation flag missing");
        Terraria.Main.Map = new MapStorage(1,2); ReadData(data, new Dictionary<ushort,ushort>{{1100,2100},{1200,2200}});
        Check(Terraria.Main.Map[0,0].Type == 2100 && Terraria.Main.Map[0,1].Type == 2200, "adjacent records bled");
    }

    private static void RleColumnBoundary()
    {
        TestHooks.Reset(2, 2); Set(0,1,1100); Set(1,0,1100); byte[] data = WriteData();
        Terraria.Main.Map = new MapStorage(2,2); ReadData(data,new Dictionary<ushort,ushort>{{1100,2100}});
        Check(Terraria.Main.Map[0,1].Type == 2100 && Terraria.Main.Map[1,0].Type == 2100, "RLE did not follow X-major/Y-minor order");
    }

    private static MapTile[] SeedRollback(int width=2, int height=2)
    {
        TestHooks.Reset(width,height); ushort value=1; for(int x=0;x<width;x++) for(int y=0;y<height;y++) Set(x,y,value++); return Terraria.Main.Map.Snapshot();
    }

    private static void UnchangedAfterInvalid(byte[] data, IDictionary<ushort,ushort> table, int width=2, int height=2)
    {
        MapTile[] before = SeedRollback(width,height); Expect<InvalidDataException>(() => ReadData(data,table));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()) && Terraria.Main.Map.SetCalls == 0, "malformed payload partially committed");
    }

    private static void ReservedFlagsRollback() => UnchangedAfterInvalid(new byte[]{0,0x80,0xE8,0x03},new Dictionary<ushort,ushort>{{1000,2000}});
    private static void MissingTypeReference() => UnchangedAfterInvalid(new byte[]{0,0,0xE8,0x03},new Dictionary<ushort,ushort>());
    private static void NullTypeTable() => UnchangedAfterInvalid(new byte[]{0,0,0xE8,0x03},null);
    private static void TruncatedTile() => UnchangedAfterInvalid(new byte[]{0,1,0xE8},new Dictionary<ushort,ushort>{{1000,2000}});
    private static void ZeroRunRejected() => UnchangedAfterInvalid(new byte[]{0}.Concat(OneRecord(1000,4,run:0)).ToArray(),new Dictionary<ushort,ushort>{{1000,2000}},1,2);
    private static void WidthWithoutRunRejected() => UnchangedAfterInvalid(new byte[]{0}.Concat(OneRecord(1000,8)).ToArray(),new Dictionary<ushort,ushort>{{1000,2000}},1,1);
    private static void UintRunRequiresUshortFlag() => UnchangedAfterInvalid(new byte[]{0}.Concat(OneRecord(1000,0x14,run:1)).ToArray(),new Dictionary<ushort,ushort>{{1000,2000}},1,2);
    private static void RunPastEnd() => UnchangedAfterInvalid(new byte[]{0}.Concat(OneRecord(1000,4,run:2)).ToArray(),new Dictionary<ushort,ushort>{{1000,2000}},1,2);
    private static void ContinuationPastEnd() => UnchangedAfterInvalid(new byte[]{0}.Concat(OneRecord(1000,0x20)).ToArray(),new Dictionary<ushort,ushort>{{1000,2000}},1,1);

    private static void PrefixRollback()
    {
        byte[] first = OneRecord(1000,0x20); byte[] second = OneRecord(1000,0x80);
        UnchangedAfterInvalid(new byte[]{0}.Concat(first).Concat(second).ToArray(),new Dictionary<ushort,ushort>{{1000,2000}},1,2);
    }

    private static void TrailingBytesRollback()
        => UnchangedAfterInvalid(new byte[]{0}.Concat(OneRecord(1000)).Concat(new byte[]{99}).ToArray(),new Dictionary<ushort,ushort>{{1000,2000}},1,1);

    private static void NonCanonicalRun()
        => UnchangedAfterInvalid(new byte[]{0}.Concat(OneRecord(1000,12,run:1)).ToArray(),new Dictionary<ushort,ushort>{{1000,2000}},1,3);

    private static void CommitOnce()
    {
        TestHooks.Reset(1,3); byte[] data = new byte[]{0}.Concat(OneRecord(1000,4,run:2)).ToArray();
        ReadData(data,new Dictionary<ushort,ushort>{{1000,2000}});
        Check(Terraria.Main.Map.SetCalls == 3 && Enumerable.Range(0,3).All(y=>Terraria.Main.Map[0,y].Type==2000),"commit count/state mismatch");
    }

    private static void MissingContentMapsZero()
    {
        TestHooks.Reset(1, 1);
        ReadFull(FullFrame(new[]{((ushort)1000,true,"Gone","Tile",(ushort)0)},new byte[]{0}.Concat(OneRecord(1000)).ToArray()));
        Check(Terraria.Main.Map[0,0].Type == 0,"missing content did not map to zero");
    }

    private static void SkippedCellsUntouched()
    {
        TestHooks.Reset(1,3); Set(0,0,7); Set(0,1,8); Set(0,2,9);
        ReadData(new byte[]{1}.Concat(OneRecord(1000)).Concat(new byte[]{1}).ToArray(),new Dictionary<ushort,ushort>{{1000,2000}});
        Check(Terraria.Main.Map[0,0].Type==7 && Terraria.Main.Map[0,1].Type==2000 && Terraria.Main.Map[0,2].Type==9,"skipped cells changed");
    }

    private static void FileWriteExtension()
    {
        Set(0,0,1100); MapLiquidIO.WriteModFile("world.map",false);
        Check(FileUtilities.Files.ContainsKey(("world.tlmap",false)) && FileUtilities.WriteCalls==1,"wrong file extension/write count");
    }

    private static string TempMapPath()
        => Path.Combine(Path.GetTempPath(),"gcb-modliquid-"+Guid.NewGuid().ToString("N")+".map");

    private static void LocalDelete()
    {
        string source=TempMapPath(), side=Path.ChangeExtension(source,".tlmap"); File.WriteAllText(side,"old");
        try { MapLiquidIO.WriteModFile(source,false); Check(!File.Exists(side) && FileUtilities.WriteCalls==0,"local sidecar not deleted"); }
        finally { if(File.Exists(side)) File.Delete(side); }
    }

    private static void CloudDelete()
    {
        SocialAPI.Cloud=new CloudSocialModule(); MapLiquidIO.WriteModFile("world.map",true);
        Check(SocialAPI.Cloud.Deleted.SequenceEqual(new[]{"world.tlmap"}) && FileUtilities.WriteCalls==0,"cloud sidecar not deleted");
    }

    private static void MissingCloudNoLocalDelete()
    {
        string source=TempMapPath(), side=Path.ChangeExtension(source,".tlmap"); File.WriteAllText(side,"local"); SocialAPI.Cloud=null;
        try { MapLiquidIO.WriteModFile(source,true); Check(File.Exists(side),"cloud operation deleted local path"); }
        finally { if(File.Exists(side)) File.Delete(side); }
    }

    private static void MissingReadNoRead()
    {
        MapLiquidIO.ReadModFile("missing.map",false);
        Check(FileUtilities.ExistsCalls==1 && FileUtilities.ReadCalls==0,"missing target was read");
    }

    private static void FileReadApplies()
    {
        TestHooks.Reset(1, 1);
        RegisterTile(1200,lookup:1500); byte[] frame=FullFrame(new[]{((ushort)1200,true,"Example","Tile",(ushort)0)},new byte[]{0}.Concat(OneRecord(1200)).ToArray());
        FileUtilities.Files[("world.tlmap",false)]=frame; MapLiquidIO.ReadModFile("world.map",false);
        Check(FileUtilities.ReadCalls==1 && Terraria.Main.Map[0,0].Type==1500,"file wrapper did not apply payload");
    }

    private static void MalformedFileRollback()
    {
        MapTile[] before=SeedRollback(); byte[] payload=new byte[]{0}.Concat(OneRecord(1000,0x20)).Concat(OneRecord(1000,0x80)).ToArray();
        FileUtilities.Files[("world.tlmap",false)]=FullFrame(new[]{((ushort)1000,true,"Gone","Tile",(ushort)0)},payload);
        Expect<InvalidDataException>(()=>MapLiquidIO.ReadModFile("world.map",false));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()) && Terraria.Main.Map.SetCalls==0,"malformed file partially committed");
    }

    private static void WriterFailurePreservesStream()
    {
        TestHooks.Reset(1, 1); Set(0, 0, 1200); RegisterTile(1200, lookup: 1200);
        TileLoader.BeforeGetTile = _ => throw new InvalidOperationException("registry changed");
        using var stream = new MemoryStream(); stream.Write(new byte[] { 7, 8, 9 });
        using var writer = new BinaryWriter(stream);
        Expect<InvalidDataException>(() => MapLiquidIO.WriteModMap(writer));
        Check(stream.Position == 3 && stream.ToArray().SequenceEqual(new byte[] { 7, 8, 9 }), "failed preparation changed destination stream");
    }

    private static void WriterUsesOneMapSnapshot()
    {
        TestHooks.Reset(1, 1); Set(0, 0, 1200); RegisterTile(1200, lookup: 1200);
        TileLoader.BeforeGetTile = _ => Set(0, 0, 1300);
        byte[] bytes = WriteMap(out bool has); Check(has, "snapshot was not written");
        using var reader = new BinaryReader(new MemoryStream(bytes));
        Check(reader.ReadUInt16() == 1 && reader.ReadUInt16() == 1200, "snapshot header identity changed");
        reader.ReadBoolean(); reader.ReadString(); reader.ReadString(); reader.ReadUInt16();
        Check(reader.ReadByte() == 0, "snapshot payload skip mismatch");
        reader.ReadByte();
        Check(reader.ReadUInt16() == 1200, "payload was reread from a later map generation");
    }

    private static void WriterRejectsAmbiguousRegistry()
    {
        TestHooks.Reset(1, 1); Set(0, 0, 1200); RegisterTile(1200, lookup: 1200); RegisterWall(1200, lookup: 1200);
        using var stream = new MemoryStream(); using var writer = new BinaryWriter(stream);
        Expect<InvalidDataException>(() => MapLiquidIO.WriteModMap(writer));
        Check(stream.Length == 0, "ambiguous registry emitted bytes");
    }

    private static void WriterRejectsLookupBelowRange()
    {
        TestHooks.Reset(1, 1); Set(0, 0, 1200); RegisterTile(1200, lookup: 999, options: 300);
        using var stream = new MemoryStream(); using var writer = new BinaryWriter(stream);
        Expect<InvalidDataException>(() => MapLiquidIO.WriteModMap(writer));
        Check(stream.Length == 0, "invalid lookup emitted bytes");
    }

    private static void WriterRejectsUnrepresentableOption()
    {
        TestHooks.Reset(1, 1); Set(0, 0, 1203); RegisterTile(1203, lookup: 1200, options: 3);
        using var stream = new MemoryStream(); using var writer = new BinaryWriter(stream);
        Expect<InvalidDataException>(() => MapLiquidIO.WriteModMap(writer));
        Check(stream.Length == 0, "out-of-range writer option emitted bytes");
    }

    private static void FileWriteFailurePerformsNoIo()
    {
        TestHooks.Reset(1, 1); Set(0, 0, 1200); RegisterTile(1200, lookup: 1200);
        FileUtilities.Files[("world.tlmap", false)] = new byte[] { 42 };
        TileLoader.BeforeGetTile = _ => throw new InvalidOperationException("registry changed");
        Expect<InvalidDataException>(() => MapLiquidIO.WriteModFile("world.map", false));
        Check(FileUtilities.WriteCalls == 0 && FileUtilities.Files[("world.tlmap", false)].SequenceEqual(new byte[] { 42 }), "failed save performed file I/O");
    }

    private static void NontileIdentityAmbiguity()
    {
        TestHooks.Reset(1, 1); RegisterLiquid(1300, name: "Shared", lookup: 1300); RegisterWall(1400, name: "Shared", lookup: 1400);
        MapTile[] before = Terraria.Main.Map.Snapshot();
        byte[] frame = FullFrame(new[] { ((ushort)1300, false, "Example", "Shared", (ushort)0) }, new byte[] { 0 }.Concat(OneRecord(1300)).ToArray());
        Expect<InvalidDataException>(() => ReadFull(frame));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()) && Terraria.Main.Map.SetCalls == 0, "ambiguous nontile identity committed");
    }

    private static void ResolvedLookupBelowRange()
    {
        TestHooks.Reset(1, 1); RegisterTile(1200, lookup: 999, options: 4); MapTile[] before = Terraria.Main.Map.Snapshot();
        byte[] frame = FullFrame(new[] { ((ushort)1200, true, "Example", "Tile", (ushort)0) }, new byte[] { 0 }.Concat(OneRecord(1200)).ToArray());
        Expect<InvalidDataException>(() => ReadFull(frame));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()), "below-range lookup committed");
    }

    private static void ResolvedLookupOverflow()
    {
        TestHooks.Reset(1, 1); RegisterTile(1200, lookup: ushort.MaxValue, options: 2); MapTile[] before = Terraria.Main.Map.Snapshot();
        byte[] frame = FullFrame(new[] { ((ushort)1200, true, "Example", "Tile", (ushort)1) }, new byte[] { 0 }.Concat(OneRecord(1200)).ToArray());
        Expect<InvalidDataException>(() => ReadFull(frame));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()), "overflowed lookup committed");
    }

    private static void ResolvedContentRequiresOption()
    {
        TestHooks.Reset(1, 1); RegisterTile(1200, lookup: 1200, options: 0); MapTile[] before = Terraria.Main.Map.Snapshot();
        byte[] frame = FullFrame(new[] { ((ushort)1200, true, "Example", "Tile", (ushort)0) }, new byte[] { 0 }.Concat(OneRecord(1200)).ToArray());
        Expect<InvalidDataException>(() => ReadFull(frame));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()), "zero-option content committed");
    }

    private static byte[] ValidSingleTileFrame()
        => FullFrame(new[] { ((ushort)1200, true, "Example", "Tile", (ushort)0) }, new byte[] { 0 }.Concat(OneRecord(1200)).ToArray());

    private static void WorldSwapDuringResolution()
    {
        TestHooks.Reset(1, 1); RegisterTile(1200, lookup: 1500); Set(0, 0, 77); WorldMap original = Terraria.Main.Map;
        WorldMap replacement = new MapStorage(1, 1); replacement[0, 0] = MapTile.Create(88, 255, 0);
        ModContent.BeforeTryFind = (type, _, _) => { if (type == typeof(ModTile)) Terraria.Main.Map = replacement; };
        Expect<InvalidDataException>(() => ReadFull(ValidSingleTileFrame()));
        Check(original[0, 0].Type == 77 && replacement[0, 0].Type == 88 && original.SetCalls == 0 && replacement.SetCalls == 0, "world swap received a stale commit");
    }

    private static void DimensionChangeDuringResolution()
    {
        TestHooks.Reset(1, 1); RegisterTile(1200, lookup: 1500); Set(0, 0, 77); WorldMap original = Terraria.Main.Map;
        ModContent.BeforeTryFind = (type, _, _) => { if (type == typeof(ModTile)) Terraria.Main.maxTilesY = 2; };
        Expect<InvalidDataException>(() => ReadFull(ValidSingleTileFrame()));
        Check(original[0, 0].Type == 77 && original.SetCalls == 0, "dimension change received a stale commit");
    }

    private static void CommitFailureRollsBack()
    {
        TestHooks.Reset(1, 3); Set(0, 0, 1); Set(0, 1, 2); Set(0, 2, 3); MapTile[] before = Terraria.Main.Map.Snapshot();
        ((MapStorage)Terraria.Main.Map).FailOnSetAttempt = 2;
        ((MapStorage)Terraria.Main.Map).MutateBeforeSetFailure = true;
        byte[] payload = new byte[] { 0 }.Concat(OneRecord(1000, 4, run: 2)).ToArray();
        Expect<InvalidDataException>(() => ReadData(payload, new Dictionary<ushort, ushort> { [1000] = 2000 }));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()), "failed commit left a written prefix");
    }

    private static void FileCommitFailureRollsBack()
    {
        TestHooks.Reset(1, 3); RegisterTile(1200, lookup: 1500); Set(0, 0, 1); Set(0, 1, 2); Set(0, 2, 3); MapTile[] before = Terraria.Main.Map.Snapshot();
        ((MapStorage)Terraria.Main.Map).FailOnSetAttempt = 2;
        ((MapStorage)Terraria.Main.Map).MutateBeforeSetFailure = true;
        byte[] payload = new byte[] { 0 }.Concat(OneRecord(1200, 4, run: 2)).ToArray();
        FileUtilities.Files[("world.tlmap", false)] = FullFrame(new[] { ((ushort)1200, true, "Example", "Tile", (ushort)0) }, payload);
        Expect<InvalidDataException>(() => MapLiquidIO.ReadModFile("world.map", false));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()), "file commit failure left a written prefix");
    }

    private static Instruction[] Anchor(string method, int pathLocal = 3, int cloudLocal = 7)
        => new[] { Instruction.Ldloc(pathLocal), Instruction.Ldloc(cloudLocal), Instruction.Call("Terraria.ModLoader.IO.MapIO", method) };

    private static ILContext DuplicateAnchors(string method)
        => new ILContext(Anchor(method).Concat(new[] { Instruction.Other() }).Concat(Anchor(method, 9, 10)).ToArray());

    private static void SaveHookForwardsUniqueAnchor()
    {
        TestHooks.Reset(1, 1); Set(0, 0, 1200); ILContext context = new ILContext(Anchor("WriteModFile"));
        MapHelperHooks.SaveTLMap(context);
        Check(context.Emitted.Count == 3 && (int)context.Emitted[0].Value == 3 && (int)context.Emitted[1].Value == 7, "save hook did not preserve locals");
        ((Action<string, bool>)context.Emitted[2].Value)("world.map", false);
        Check(FileUtilities.Files.ContainsKey(("world.tlmap", false)), "save hook did not forward to sidecar writer");
    }

    private static void SaveHookRejectsMissingAnchor()
    {
        ILContext context = new ILContext(Instruction.Other());
        Expect<InvalidOperationException>(() => MapHelperHooks.SaveTLMap(context));
        Check(context.Emitted.Count == 0, "missing save anchor emitted partial IL");
    }

    private static void SaveHookRejectsDuplicateAnchor()
    {
        ILContext context = DuplicateAnchors("WriteModFile");
        Expect<InvalidOperationException>(() => MapHelperHooks.SaveTLMap(context));
        Check(context.Emitted.Count == 0, "ambiguous save anchor emitted partial IL");
    }

    private static void LoadHookForwardsUniqueAnchor()
    {
        TestHooks.Reset(1, 1); RegisterTile(1200, lookup: 1500); FileUtilities.Files[("world.tlmap", false)] = ValidSingleTileFrame();
        ILContext context = new ILContext(Anchor("ReadModFile")); WorldMap destination = Terraria.Main.Map;
        WorldMapHooks.InitaliseTLMap(context);
        Check(context.Emitted.Count == 3 && (int)context.Emitted[0].Value == 3 && (int)context.Emitted[1].Value == 7, "load hook did not preserve locals");
        ((Action<string, bool>)context.Emitted[2].Value)("world.map", false);
        Check(destination[0, 0].Type == 1500, "load hook did not forward to sidecar reader");
    }

    private static void LoadHookRejectsMissingAnchor()
    {
        ILContext context = new ILContext(Instruction.Other());
        Expect<InvalidOperationException>(() => WorldMapHooks.InitaliseTLMap(context));
        Check(context.Emitted.Count == 0, "missing load anchor emitted partial IL");
    }

    private static void LoadHookRejectsDuplicateAnchor()
    {
        ILContext context = DuplicateAnchors("ReadModFile");
        Expect<InvalidOperationException>(() => WorldMapHooks.InitaliseTLMap(context));
        Check(context.Emitted.Count == 0, "ambiguous load anchor emitted partial IL");
    }

    private static IList<MapEntry> Entries(string prefix, params int[] colors)
        => colors.Select((color, option) => new MapEntry(new Color(color), new LocalizedText(prefix + option))).ToList();

    private static ModLiquid ConfigureLiquid(ushort type, string name, params int[] colors)
    {
        LiquidLoader.LiquidCount = Math.Max(LiquidLoader.LiquidCount, type + 1);
        MapLiquidLoader.liquidEntries[type] = Entries(name, colors);
        var liquid = new ModLiquid { Type = type, Name = name, Mod = new Mod { Name = "Example" } };
        LiquidLoader.Liquids[type] = liquid;
        ModContent.Register("Example", name, liquid);
        return liquid;
    }

    private static void PublishFresh()
    {
        IList<Color> colors = new List<Color>();
        IList<LocalizedText> names = new List<LocalizedText>();
        MapLiquidLoader.PublishEntries(ref colors, ref names);
    }

    private static void RegistryPublicationIsAtomicDeterministicAndCoherent()
    {
        ConfigureLiquid(7, "Seven", 70);
        ConfigureLiquid(5, "Five", 50, 51);
        Func<string, int, int, string> existing = (name, _, _) => name + "!";
        MapLoader.nameFuncs[900] = existing;
        IList<Color> colors = new List<Color> { new Color(1) };
        IList<LocalizedText> names = new List<LocalizedText> { new LocalizedText("base") };
        MapLiquidLoader.liquidLookup = new ushort[] { 80, 81, 82, 83 };
        IList<Color> originalColors = colors;
        IList<LocalizedText> originalNames = names;
        uint generation = MapLiquidLoader.Generation;

        MapLiquidLoader.PublishEntries(ref colors, ref names);

        Check(!ReferenceEquals(colors, originalColors) && !ReferenceEquals(names, originalNames), "publication reused caller-owned tables");
        Check(originalColors.Count == 1 && originalNames.Count == 1, "publication mutated the caller's old tables");
        Check(colors.Select(color => color.Value).SequenceEqual(new[] { 1, 50, 51, 70 }), "liquids were not published in type/option order");
        Check(names.Select(name => name.Value).SequenceEqual(new[] { "base", "Five0", "Five1", "Seven0" }), "published names are misaligned");
        Check(MapLiquidLoader.liquidLookup.Length == 8 && MapLiquidLoader.liquidLookup.Take(4).SequenceEqual(new ushort[] { 80, 81, 82, 83 }) && MapLiquidLoader.liquidLookup[5] == 1001 && MapLiquidLoader.liquidLookup[7] == 1003, "liquid lookup bases or vanilla prefix are incoherent");
        Check(MapLiquidLoader.entryToLiquid.Count == 3 && MapLiquidLoader.entryToLiquid[1001] == 5 && MapLiquidLoader.entryToLiquid[1002] == 5 && MapLiquidLoader.entryToLiquid[1003] == 7, "reverse liquid ownership is incoherent");
        Check(MapLoader.nameFuncs.ContainsKey(1001) && MapLoader.nameFuncs.ContainsKey(1002) && MapLoader.nameFuncs.ContainsKey(1003) && ReferenceEquals(MapLoader.nameFuncs[900], existing), "name callbacks were not published coherently");
        Check(MapLiquidLoader.Generation == generation + 1, "successful publication did not advance exactly one generation");
    }

    private static void RegistryRejectsOutOfRangeTypeWithoutMutation()
    {
        ConfigureLiquid(5, "Valid", 5);
        MapLiquidLoader.liquidEntries[3] = Entries("Vanilla", 3);
        MapLiquidLoader.entryToLiquid[1700] = 5;
        MapLiquidLoader.liquidLookup = new ushort[8];
        MapLiquidLoader.liquidLookup[5] = 1700;
        Func<string, int, int, string> callback = (name, _, _) => name;
        MapLoader.nameFuncs[1700] = callback;
        IList<Color> colors = new List<Color> { new Color(9) };
        IList<LocalizedText> names = new List<LocalizedText> { new LocalizedText("old") };
        uint generation = MapLiquidLoader.Generation;

        Expect<InvalidOperationException>(() => MapLiquidLoader.PublishEntries(ref colors, ref names));

        Check(colors.Count == 1 && colors[0].Value == 9 && names.Count == 1 && names[0].Value == "old", "failed publication changed caller tables");
        Check(MapLiquidLoader.entryToLiquid.Count == 1 && MapLiquidLoader.entryToLiquid[1700] == 5 && MapLiquidLoader.liquidLookup[5] == 1700, "failed publication changed liquid mappings");
        Check(MapLoader.nameFuncs.Count == 1 && ReferenceEquals(MapLoader.nameFuncs[1700], callback), "failed publication changed name callbacks");
        Check(MapLiquidLoader.Generation == generation, "failed publication advanced the generation");
    }

    private static void RegistryRejectsMapTypeCollisionWithoutMutation()
    {
        ConfigureLiquid(5, "Liquid", 5);
        MapLoader.entryToTile[1000] = 12;
        IList<Color> colors = new List<Color>();
        IList<LocalizedText> names = new List<LocalizedText>();
        uint generation = MapLiquidLoader.Generation;
        Expect<InvalidOperationException>(() => MapLiquidLoader.PublishEntries(ref colors, ref names));
        Check(colors.Count == 0 && names.Count == 0 && MapLiquidLoader.entryToLiquid.Count == 0 && MapLiquidLoader.Generation == generation, "collision failure was not atomic");
    }

    private static void RegistryRejectsUshortOverflowWithoutMutation()
    {
        ConfigureLiquid(5, "Liquid", 5);
        MapHelper.modPosition = ushort.MaxValue;
        IList<Color> colors = new List<Color> { new Color(1) };
        IList<LocalizedText> names = new List<LocalizedText> { new LocalizedText("base") };
        uint generation = MapLiquidLoader.Generation;
        Expect<InvalidOperationException>(() => MapLiquidLoader.PublishEntries(ref colors, ref names));
        Check(colors.Count == 1 && names.Count == 1 && MapLiquidLoader.entryToLiquid.Count == 0 && MapLiquidLoader.Generation == generation, "overflow failure was not atomic");
    }

    private static void RegistryRejectsNullLocalizedNameWithoutMutation()
    {
        LiquidLoader.LiquidCount = 6;
        MapLiquidLoader.liquidEntries[5] = new List<MapEntry> { new MapEntry(new Color(5), null, (name, _, _) => name) };
        IList<Color> colors = new List<Color>();
        IList<LocalizedText> names = new List<LocalizedText>();
        uint generation = MapLiquidLoader.Generation;
        Expect<InvalidOperationException>(() => MapLiquidLoader.PublishEntries(ref colors, ref names));
        Check(MapLiquidLoader.entryToLiquid.Count == 0 && MapLiquidLoader.Generation == generation, "null-name failure mutated registry state");
    }

    private static void RegistryRejectsNullNameCallbackWithoutMutation()
    {
        LiquidLoader.LiquidCount = 6;
        MapLiquidLoader.liquidEntries[5] = new List<MapEntry> { new MapEntry(new Color(5), new LocalizedText("name"), null) };
        IList<Color> colors = new List<Color>();
        IList<LocalizedText> names = new List<LocalizedText>();
        uint generation = MapLiquidLoader.Generation;
        Expect<InvalidOperationException>(() => MapLiquidLoader.PublishEntries(ref colors, ref names));
        Check(MapLiquidLoader.entryToLiquid.Count == 0 && MapLiquidLoader.Generation == generation, "null-callback failure mutated registry state");
    }

    private static void AssertUnload(bool dedicated)
    {
        MapLiquidLoader.liquidLookup = new ushort[] { 80, 81, 82, 83 };
        ConfigureLiquid(5, "Liquid", 5, 6);
        MapLoader.nameFuncs[900] = (name, _, _) => name;
        PublishFresh();
        MapLiquidLoader.initialized = true;
        Terraria.Main.dedServ = dedicated;
        uint generation = MapLiquidLoader.Generation;

        MapLiquidLoader.UnloadModMap();

        Check(MapLiquidLoader.liquidEntries.Count == 0 && MapLiquidLoader.entryToLiquid.Count == 0, "unload retained liquid entries");
        Check(MapLiquidLoader.liquidLookup.SequenceEqual(new ushort[] { 80, 81, 82, 83 }), "unload did not preserve only the vanilla lookup prefix");
        Check(!MapLiquidLoader.initialized && MapLoader.nameFuncs.Count == 1 && MapLoader.nameFuncs.ContainsKey(900), "unload did not remove only owned callbacks");
        Check(MapLiquidLoader.Generation == generation + 1, "unload did not advance exactly one generation");
    }

    private static void ClientUnloadClearsAllPublishedState() => AssertUnload(false);
    private static void DedicatedServerUnloadClearsAllPublishedState() => AssertUnload(true);

    private static void MapOptionResolvesFromPublishedBaseOnce()
    {
        ModLiquid liquid = RegisterLiquid(1302, lookup: 1300, options: 4);
        int calls = 0;
        liquid.MapOption = (i, j) => { calls++; Check(i == 17 && j == 23, "map coordinates were not forwarded"); return 1; };
        ushort mapType = 1302;
        MapLiquidLoader.ModMapOption(ref mapType, 17, 23);
        Check(calls == 1 && mapType == 1301, "map option was not resolved once from the published base");
    }

    private static void InvalidMapOptionPreservesInput()
    {
        ModLiquid liquid = RegisterLiquid(1301, lookup: 1300, options: 2);
        int calls = 0;
        liquid.MapOption = (_, _) => { calls++; return 2; };
        ushort mapType = 1301;
        Expect<ArgumentOutOfRangeException>(() => MapLiquidLoader.ModMapOption(ref mapType, 0, 0));
        Check(calls == 1 && mapType == 1301, "invalid option changed the caller's map type");
    }

    private static void MapOptionRejectsGenerationChange()
    {
        ModLiquid liquid = RegisterLiquid(1301, lookup: 1300, options: 2);
        liquid.MapOption = (_, _) => { PublishFresh(); return 0; };
        ushort mapType = 1301;
        Expect<InvalidOperationException>(() => MapLiquidLoader.ModMapOption(ref mapType, 0, 0));
        Check(mapType == 1301, "generation change committed a stale option");
    }

    private static void MapOptionRejectsDirectTopologyChange()
    {
        ModLiquid liquid = RegisterLiquid(1301, lookup: 1300, options: 2);
        liquid.MapOption = (_, _) => { MapLiquidLoader.entryToLiquid[1301] = 9; return 0; };
        ushort mapType = 1301;
        Expect<InvalidOperationException>(() => MapLiquidLoader.ModMapOption(ref mapType, 0, 0));
        Check(mapType == 1301, "topology change committed a stale option");
    }

    private static void MapOptionRejectsLoaderGenerationChangeBeforeCallback()
    {
        ModLiquid liquid = RegisterLiquid(1301, lookup: 1300, options: 2);
        int optionCalls = 0;
        liquid.MapOption = (_, _) => { optionCalls++; return 0; };
        bool published = false;
        LiquidLoader.BeforeGetLiquid = _ => RepublishRegistryOnce(ref published);
        ushort mapType = 1301;
        Expect<InvalidOperationException>(() => MapLiquidLoader.ModMapOption(ref mapType, 0, 0));
        Check(optionCalls == 0 && mapType == 1301, "loader-side generation change invoked or committed a stale callback");
    }

    private static void MapOptionRejectsOwnerAliasOutsideRange()
    {
        ModLiquid liquid = RegisterLiquid(1800, lookup: 1300, options: 2);
        int optionCalls = 0;
        liquid.MapOption = (_, _) => { optionCalls++; return 0; };
        ushort mapType = 1800;
        Expect<InvalidOperationException>(() => MapLiquidLoader.ModMapOption(ref mapType, 0, 0));
        Check(optionCalls == 0 && mapType == 1800, "out-of-range owner alias invoked or committed an option");
    }

    private static void RepublishRegistryOnce(ref bool published)
    {
        if (published) return;
        published = true;
        PublishFresh();
    }

    private static void WriterRejectsRegistryRepublicationBeforeOutput()
    {
        TestHooks.Reset(1, 1); Set(0, 0, 1300); RegisterLiquid(1300, lookup: 1300, options: 2);
        bool published = false;
        LiquidLoader.BeforeGetLiquid = _ => RepublishRegistryOnce(ref published);
        using var stream = new MemoryStream(); stream.Write(new byte[] { 4, 5 });
        using var writer = new BinaryWriter(stream);
        Expect<InvalidDataException>(() => MapLiquidIO.WriteModMap(writer));
        Check(stream.Position == 2 && stream.ToArray().SequenceEqual(new byte[] { 4, 5 }), "registry race emitted partial sidecar bytes");
    }

    private static byte[] ValidSingleLiquidFrame()
        => FullFrame(new[] { ((ushort)1300, false, "Example", "Liquid", (ushort)0) }, new byte[] { 0 }.Concat(OneRecord(1300)).ToArray());

    private static void ReaderRejectsRegistryRepublicationBeforeCommit()
    {
        TestHooks.Reset(1, 1); RegisterLiquid(1300, lookup: 1300, options: 2); Set(0, 0, 77); MapTile[] before = Terraria.Main.Map.Snapshot();
        bool published = false;
        ModContent.BeforeTryFind = (type, _, _) => { if (type == typeof(ModLiquid)) RepublishRegistryOnce(ref published); };
        Expect<InvalidDataException>(() => ReadFull(ValidSingleLiquidFrame()));
        Check(before.SequenceEqual(Terraria.Main.Map.Snapshot()) && Terraria.Main.Map.SetCalls == 0, "registry race committed decoded map cells");
    }

    private static void FileWriterRepublicationFailurePerformsNoIo()
    {
        TestHooks.Reset(1, 1); Set(0, 0, 1300); RegisterLiquid(1300, lookup: 1300, options: 2);
        FileUtilities.Files[("world.tlmap", false)] = new byte[] { 42 };
        bool published = false;
        LiquidLoader.BeforeGetLiquid = _ => RepublishRegistryOnce(ref published);
        Expect<InvalidDataException>(() => MapLiquidIO.WriteModFile("world.map", false));
        Check(FileUtilities.WriteCalls == 0 && FileUtilities.Files[("world.tlmap", false)].SequenceEqual(new byte[] { 42 }), "registry race performed file output");
    }

    private static void FileReaderRepublicationFailurePreservesMap()
    {
        TestHooks.Reset(1, 1); RegisterLiquid(1300, lookup: 1300, options: 2); Set(0, 0, 77); MapTile[] before = Terraria.Main.Map.Snapshot();
        FileUtilities.Files[("world.tlmap", false)] = ValidSingleLiquidFrame();
        bool published = false;
        ModContent.BeforeTryFind = (type, _, _) => { if (type == typeof(ModLiquid)) RepublishRegistryOnce(ref published); };
        Expect<InvalidDataException>(() => MapLiquidIO.ReadModFile("world.map", false));
        Check(FileUtilities.ReadCalls == 1 && before.SequenceEqual(Terraria.Main.Map.Snapshot()) && Terraria.Main.Map.SetCalls == 0, "file registry race changed the destination map");
    }

    private static Instruction[] FinishSetupAnchor(int colorLocal = 2, int nameLocal = 5)
        => new[] { Instruction.Stloc(colorLocal), Instruction.Newobj(typeof(List<LocalizedText>).FullName), Instruction.Stloc(nameLocal) };

    private static void FinishSetupHookForwardsUniqueAnchor()
    {
        ConfigureLiquid(5, "Liquid", 5);
        ILContext context = new ILContext(FinishSetupAnchor());
        MapLoaderHooks.AddLiquidToFinishSetup(context);
        Check(context.Emitted.Count == 3 && (int)context.Emitted[0].Value == 2 && (int)context.Emitted[1].Value == 5, "finish-setup hook did not preserve table locals");
        object[] args = { new List<Color>(), new List<LocalizedText>() };
        ((Delegate)context.Emitted[2].Value).DynamicInvoke(args);
        Check(((IList<Color>)args[0]).Count == 1 && ((IList<LocalizedText>)args[1]).Count == 1 && MapLiquidLoader.entryToLiquid[1000] == 5, "finish-setup hook did not publish through the production registry");
    }

    private static void FinishSetupHookRejectsMissingAnchor()
    {
        ILContext context = new ILContext(Instruction.Stloc(2), Instruction.Newobj("Wrong.Type"), Instruction.Stloc(5));
        Expect<InvalidOperationException>(() => MapLoaderHooks.AddLiquidToFinishSetup(context));
        Check(context.Emitted.Count == 0, "missing finish-setup anchor emitted partial IL");
    }

    private static void FinishSetupHookRejectsDuplicateAnchor()
    {
        ILContext context = new ILContext(FinishSetupAnchor().Concat(new[] { Instruction.Other() }).Concat(FinishSetupAnchor(8, 9)).ToArray());
        Expect<InvalidOperationException>(() => MapLoaderHooks.AddLiquidToFinishSetup(context));
        Check(context.Emitted.Count == 0, "ambiguous finish-setup anchor emitted partial IL");
    }

    private static Instruction[] LiquidLookupAnchor(int mapIndex = 6, int mapTile = 9)
        => new[] { Instruction.Ldsfld("Terraria.Map.MapHelper", "liquidPosition"), Instruction.Ldloc(mapIndex), Instruction.Add(), Instruction.Stloc(mapTile) };

    private static Instruction[] ModMapOptionAnchor(int mapType = 11)
        => new[] { Instruction.Ldloca(mapType), Instruction.Ldarg(0), Instruction.Ldarg(1), Instruction.Call("Terraria.ModLoader.MapLoader", "ModMapOption") };

    private static void LiquidLookupHookForwardsBothUniqueAnchors()
    {
        ILContext context = new ILContext(LiquidLookupAnchor().Concat(new[] { Instruction.Other() }).Concat(ModMapOptionAnchor()).ToArray());
        MapHelperHooks.AddLiquidMapEntrys(context);
        Check(context.Emitted.Count == 7 && (int)context.Emitted[0].Value == 9 && (int)context.Emitted[1].Value == 6 && (int)context.Emitted[3].Value == 11, "liquid lookup hook did not preserve locals");
        MapLiquidLoader.liquidLookup = new ushort[8]; MapLiquidLoader.liquidLookup[6] = 1400;
        object[] lookupArgs = { 0, 6 }; ((Delegate)context.Emitted[2].Value).DynamicInvoke(lookupArgs);
        Check((int)lookupArgs[0] == 1400, "liquid lookup delegate did not forward the lookup");
        ModLiquid liquid = RegisterLiquid(1300, lookup: 1300, options: 2); liquid.MapOption = (_, _) => 1;
        object[] optionArgs = { (ushort)1300, 4, 7 }; ((Delegate)context.Emitted[6].Value).DynamicInvoke(optionArgs);
        Check((ushort)optionArgs[0] == 1301, "liquid option delegate did not forward option selection");
    }

    private static void LiquidLookupHookRejectsMissingSecondAnchor()
    {
        ILContext context = new ILContext(LiquidLookupAnchor().Concat(new[] { Instruction.Call("Wrong.Owner", "ModMapOption") }).ToArray());
        Expect<InvalidOperationException>(() => MapHelperHooks.AddLiquidMapEntrys(context));
        Check(context.Emitted.Count == 0, "missing liquid option anchor emitted partial IL");
    }

    private static void LiquidLookupHookRejectsDuplicateFirstAnchor()
    {
        ILContext context = new ILContext(LiquidLookupAnchor().Concat(LiquidLookupAnchor(7, 10)).Concat(ModMapOptionAnchor()).ToArray());
        Expect<InvalidOperationException>(() => MapHelperHooks.AddLiquidMapEntrys(context));
        Check(context.Emitted.Count == 0, "ambiguous liquid lookup anchor emitted partial IL");
    }

    private static void LiquidLookupHookRejectsReversedAnchors()
    {
        ILContext context = new ILContext(ModMapOptionAnchor().Concat(LiquidLookupAnchor()).ToArray());
        Expect<InvalidOperationException>(() => MapHelperHooks.AddLiquidMapEntrys(context));
        Check(context.Emitted.Count == 0, "reversed liquid lookup anchors emitted partial IL");
    }

    private static Instruction[] LiquidPositionAnchor(int local = 2)
        => new[] { Instruction.Ldloc(local), Instruction.Stsfld("Terraria.Map.MapHelper", "liquidPosition") };

    private static Instruction[] LiquidColorAnchor(int local = 4)
        => new[] { Instruction.Ldloc(local), Instruction.Ldelem(), Instruction.Stelem() };

    private static Instruction[] VanillaLiquidCountAnchor(int local = 4)
        => new[] { Instruction.Ldloc(local), Instruction.LdcI4(4) };

    private static void LiquidCountHookForwardsAllUniqueAnchors()
    {
        ILContext context = new ILContext(LiquidPositionAnchor().Concat(LiquidColorAnchor()).Concat(VanillaLiquidCountAnchor()).ToArray());
        MapHelperHooks.IncrimentLiquidMapEntries(context);
        Check(context.Emitted.Count == 5 && (int)context.Emitted[1].Value == 4 && (int)context.Emitted[2].Value == 2, "liquid count hook did not preserve locals");
        MapLiquidLoader.liquidLookup = new ushort[9];
        ((Delegate)context.Emitted[0].Value).DynamicInvoke();
        Check(MapLiquidLoader.liquidLookup.Length == Terraria.ID.LiquidID.Count, "liquid count hook did not reset the vanilla lookup");
        MapLiquidLoader.liquidLookup = new ushort[8];
        ((Delegate)context.Emitted[3].Value).DynamicInvoke(6, (ushort)1500);
        Check(MapLiquidLoader.liquidLookup[6] == 1500, "liquid count hook did not map the copied color");
        Check((int)((Delegate)context.Emitted[4].Value).DynamicInvoke(4) == Terraria.ID.LiquidID.Count, "liquid count hook did not replace the vanilla count");
    }

    private static void LiquidCountHookRejectsMissingThirdAnchor()
    {
        ILContext context = new ILContext(LiquidPositionAnchor().Concat(LiquidColorAnchor()).ToArray());
        Expect<InvalidOperationException>(() => MapHelperHooks.IncrimentLiquidMapEntries(context));
        Check(context.Emitted.Count == 0, "missing liquid count anchor emitted partial IL");
    }

    private static void LiquidCountHookRejectsDuplicateMiddleAnchor()
    {
        ILContext context = new ILContext(LiquidPositionAnchor().Concat(LiquidColorAnchor()).Concat(LiquidColorAnchor(7)).Concat(VanillaLiquidCountAnchor()).ToArray());
        Expect<InvalidOperationException>(() => MapHelperHooks.IncrimentLiquidMapEntries(context));
        Check(context.Emitted.Count == 0, "ambiguous liquid color anchor emitted partial IL");
    }

    private static void LiquidCountHookRejectsReversedAnchors()
    {
        ILContext context = new ILContext(LiquidColorAnchor().Concat(LiquidPositionAnchor()).Concat(VanillaLiquidCountAnchor()).ToArray());
        Expect<InvalidOperationException>(() => MapHelperHooks.IncrimentLiquidMapEntries(context));
        Check(context.Emitted.Count == 0, "reversed liquid count anchors emitted partial IL");
    }

    private static void Expect<T>(Action action) where T:Exception
    {
        try { action(); } catch(T) { return; } throw new InvalidOperationException($"expected {typeof(T).Name}");
    }
}
