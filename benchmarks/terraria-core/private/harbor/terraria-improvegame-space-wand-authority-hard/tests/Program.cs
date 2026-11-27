using System;
using System.Collections.Generic;
using System.Linq;
using ImproveGame.Content.Items;
using ImproveGame.Content.Packets;
using ImproveGame.Packets;
using ImproveGame.Packets.Items;
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.Enums;
using Terraria.ID;
using Terraria.ModLoader;

internal static class ContractProgram
{
    private static readonly Dictionary<string, Action> Cases = new()
    {
        ["direction_axes_are_stable"] = DirectionAxes,
        ["direction_diagonals_are_stable"] = DirectionDiagonals,
        ["direction_sector_boundaries_are_deterministic"] = DirectionBoundaries,
        ["line_includes_both_endpoints"] = LineIncludesEndpoints,
        ["line_rejects_unsafe_start"] = LineRejectsUnsafeStart,
        ["line_stops_before_safe_margin"] = LineStopsAtMargin,
        ["every_shape_rejects_unsafe_start"] = EveryShapeRejectsUnsafeStart,
        ["corner_vertical_first_order"] = CornerVerticalFirst,
        ["corner_horizontal_first_order"] = CornerHorizontalFirst,
        ["corner_contains_shared_vertex_once"] = CornerSharedOnce,
        ["corner_clipping_stops_remaining_leg"] = CornerClippingStops,
        ["filled_square_respects_sixty_limit"] = FilledSquareLimit,
        ["outline_square_respects_one_sixty_limit"] = OutlineSquareLimit,
        ["degenerate_square_has_unique_tiles"] = DegenerateSquareUnique,
        ["square_clips_to_safe_world"] = SquareClipsWorld,
        ["filled_circle_has_unique_interior"] = FilledCircleUnique,
        ["thin_circle_contains_only_boundary"] = ThinCircleBoundary,
        ["connected_circle_uses_cardinal_neighbor_boundary"] = ConnectedCircleBoundary,
        ["circle_radius_caps_are_enforced"] = CircleRadiusCaps,
        ["circle_clips_to_safe_world"] = CircleClipsWorld,
        ["successful_place_consumes_once"] = SuccessfulPlaceConsumesOnce,
        ["nonconsumable_material_is_not_reported"] = NonConsumableNotReported,
        ["consumption_hook_veto_keeps_valid_placement"] = ConsumptionHookVetoPlacement,
        ["tile_wand_consumes_ammo_not_wand"] = TileWandConsumesAmmo,
        ["tile_wand_ammo_veto_keeps_valid_placement"] = TileWandAmmoVetoPlacement,
        ["missing_tile_wand_ammo_is_atomic"] = MissingTileWandAmmoAtomic,
        ["loader_rejection_is_atomic"] = LoaderRejectionAtomic,
        ["failed_new_tile_place_is_atomic"] = FailedNewTilePlaceAtomic,
        ["matching_tile_reshapes_without_consumption"] = MatchingTileReshapes,
        ["disabled_replacement_is_atomic"] = DisabledReplacementAtomic,
        ["rope_cannot_replace_platform"] = RopeCannotReplacePlatform,
        ["insufficient_pick_power_is_atomic"] = InsufficientPickAtomic,
        ["successful_replacement_consumes_once"] = SuccessfulReplacementConsumes,
        ["replace_fallback_kills_then_places_once"] = ReplaceFallback,
        ["failed_replace_fallback_restores_original_tile"] = FailedReplaceFallbackRestores,
        ["solid_place_resets_external_below_slope"] = SolidResetsExternalBelow,
        ["solid_place_preserves_selected_below_slope"] = SolidPreservesSelectedBelow,
        ["unsafe_operation_stops_before_loader"] = UnsafeOperationStopsEarly,
        ["packet_requires_server_authority"] = PacketRequiresServer,
        ["packet_rejects_invalid_sender"] = PacketRejectsSender,
        ["packet_rejects_inactive_sender"] = PacketRejectsInactive,
        ["packet_rejects_invalid_enums"] = PacketRejectsEnums,
        ["packet_rejects_nonfinite_coordinates"] = PacketRejectsNonFinite,
        ["packet_operates_bottom_to_top"] = PacketBottomToTop,
        ["outline_packet_syncs_three_by_three_neighborhoods"] = OutlineSyncCoverage,
        ["filled_packet_syncs_one_bounding_region"] = FilledSyncCoverage,
        ["packet_reports_aggregated_consumption"] = PacketReportsConsumption,
        ["packet_broadcasts_one_sound_on_change"] = PacketOneSound,
        ["packet_with_no_change_emits_no_side_effect_packets"] = PacketNoChangeNoPackets,
        ["failed_replace_fallback_emits_no_packets"] = FailedReplaceFallbackNoPackets,
        ["packet_syncs_placement_despite_consumption_veto"] = PacketConsumptionVeto,
        ["shape_methods_reject_nonfinite_inputs"] = ShapeMethodsRejectNonFinite,
        ["extreme_finite_line_clips_in_drag_direction"] = ExtremeFiniteLine,
        ["extreme_finite_corner_clips_in_drag_direction"] = ExtremeFiniteCorner,
        ["extreme_finite_square_clamps_in_drag_direction"] = ExtremeFiniteSquare,
        ["failed_empty_place_restores_partial_mutation"] = FailedEmptyPlaceRestoresPartialMutation,
        ["failed_grass_place_restores_partial_mutation"] = FailedGrassPlaceRestoresPartialMutation,
        ["failed_replace_restores_before_fallback"] = FailedReplaceRestoresBeforeFallback,
        ["forbidden_replacement_preserves_block_shape"] = ForbiddenReplacementPreservesBlockShape,
        ["matching_tile_requires_pound_permission"] = MatchingTileRequiresPoundPermission,
        ["packet_syncs_slope_only_change_without_sound"] = PacketSyncsSlopeOnlyChange,
        ["packet_syncs_external_support_change"] = PacketSyncsExternalSupportChange,
        ["outline_packet_syncs_only_changed_tiles"] = OutlinePacketSyncsOnlyChangedTiles,
        ["filled_packet_bounds_only_changed_tiles"] = FilledPacketBoundsOnlyChangedTiles,
        ["failed_partial_mutation_emits_no_packets"] = FailedPartialMutationNoPackets,
        ["inventory_exhaustion_syncs_only_committed_tiles"] = InventoryExhaustionSyncsCommittedTiles,
        ["outline_dirty_sync_order_is_deterministic"] = OutlineDirtySyncOrder,
        ["false_place_with_committed_postcondition_succeeds"] = FalsePlaceWithCommittedPostcondition,
        ["true_place_without_committed_postcondition_fails"] = TruePlaceWithoutCommittedPostcondition,
        ["false_grass_place_with_committed_postcondition_succeeds"] = FalseGrassPlaceWithCommittedPostcondition,
        ["false_replace_with_committed_postcondition_succeeds"] = FalseReplaceWithCommittedPostcondition,
        ["true_replace_without_committed_postcondition_uses_fallback"] = TrueReplaceWithoutCommittedPostcondition,
        ["loader_rejection_restores_full_neighborhood"] = LoaderRejectionRestoresFullNeighborhood,
        ["failed_place_restores_full_neighborhood"] = FailedPlaceRestoresFullNeighborhood,
        ["failed_fallback_restores_full_neighborhood"] = FailedFallbackRestoresFullNeighborhood,
        ["packet_requires_held_space_wand"] = PacketRequiresHeldSpaceWand,
        ["packet_rejects_building_disabled_sender"] = PacketRejectsBuildingDisabledSender,
        ["packet_rejects_dead_sender"] = PacketRejectsDeadSender,
        ["packet_syncs_frame_only_mutation"] = PacketSyncsFrameOnlyMutation,
        ["outline_packet_syncs_committed_neighbor_mutation"] = OutlinePacketSyncsCommittedNeighborMutation,
        ["failed_neighbor_mutation_emits_no_packets"] = FailedNeighborMutationNoPackets,
        ["filled_packet_bounds_committed_neighbor_mutation"] = FilledPacketBoundsCommittedNeighborMutation,
    };

    public static int Run(string[] args)
    {
        if (args.Length != 1 || !Cases.TryGetValue(args[0], out Action test)) return 2;
        try { TestHooks.Reset(); test(); Console.WriteLine("PASS"); return 0; }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }

    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private readonly record struct ObservedTileState(bool HasTile, ushort TileType, BlockType BlockType,
        short TileFrameX, short TileFrameY, byte TileColor, bool IsActuated)
    {
        public static ObservedTileState Capture(Tile tile) => new(tile.HasTile, tile.TileType, tile.BlockType,
            tile.TileFrameX, tile.TileFrameY, tile.TileColor, tile.IsActuated);
    }

    private static Vector2 Pixel(int x, int y) => new(x * 16f, y * 16f);
    private static Point[] Select(ShapeType shape, int sx, int sy, int ex, int ey, bool control=false)
        => SpaceWand.GetSelectedTiles(shape, Pixel(sx,sy), Pixel(ex,ey), control).ToArray();

    private static void EqualPoints(IEnumerable<Point> actual, params Point[] expected)
        => Check(actual.SequenceEqual(expected), $"points differed: {string.Join(';', actual.Select(p=>$"{p.X},{p.Y}"))}");

    private static Item Solid(int type=100, int stack=20, bool consumable=true)
    {
        Main.tileSolid[type]=true;
        return new Item { type=type, stack=stack, createTile=type, consumable=consumable };
    }

    private static Player PlayerWith(Item item)
    {
        Player player=Main.player[1]; player.inventory[0]=item; return player;
    }

    private static (bool sound, Dictionary<int,int> consumed) Operate(Player player,int x=20,int y=20,PlaceType place=PlaceType.Soild,BlockType block=BlockType.Solid,HashSet<Point> selected=null)
    {
        bool sound=false; var consumed=new Dictionary<int,int>(); selected ??= new HashSet<Point>{new(x,y)};
        SpaceWand.OperateTile(player,x,y,selected,place,block,ref sound,consumed);
        return (sound,consumed);
    }

    private static SpaceWandOperation Packet(ShapeType shape, int sx=20,int sy=20,int ex=20,int ey=20,PlaceType place=PlaceType.Soild,BlockType block=BlockType.Solid,bool control=false)
    {
        SpaceWandOperation packet=SpaceWandOperation.Get(Pixel(sx,sy),Pixel(ex,ey),shape,block,place,control);
        packet.Sender=1;
        return packet;
    }

    private static void DirectionAxes()
    {
        Vector2 o=Pixel(20,20);
        Check(SpaceWand.GetDirection(o,Pixel(21,20))==SpaceWand.Direction.Right,"right");
        Check(SpaceWand.GetDirection(o,Pixel(20,21))==SpaceWand.Direction.Down,"down");
        Check(SpaceWand.GetDirection(o,Pixel(19,20))==SpaceWand.Direction.Left,"left");
        Check(SpaceWand.GetDirection(o,Pixel(20,19))==SpaceWand.Direction.Up,"up");
    }

    private static void DirectionDiagonals()
    {
        Vector2 o=Pixel(20,20);
        Check(SpaceWand.GetDirection(o,Pixel(21,21))==SpaceWand.Direction.RightDown,"right-down");
        Check(SpaceWand.GetDirection(o,Pixel(19,21))==SpaceWand.Direction.LeftDown,"left-down");
        Check(SpaceWand.GetDirection(o,Pixel(19,19))==SpaceWand.Direction.LeftUp,"left-up");
        Check(SpaceWand.GetDirection(o,Pixel(21,19))==SpaceWand.Direction.RightUp,"right-up");
    }

    private static void DirectionBoundaries()
    {
        Vector2 o=new(100,100); float r=64, a=MathF.PI/8;
        Check(SpaceWand.GetDirection(o,new(o.X+MathF.Cos(a)*r,o.Y+MathF.Sin(a)*r))==SpaceWand.Direction.RightDown,"positive boundary");
        Check(SpaceWand.GetDirection(o,new(o.X+MathF.Cos(-a)*r,o.Y+MathF.Sin(-a)*r))==SpaceWand.Direction.RightUp,"negative boundary");
    }

    private static void LineIncludesEndpoints() => EqualPoints(Select(ShapeType.Line,20,20,23,20),new Point(20,20),new Point(21,20),new Point(22,20),new Point(23,20));
    private static void LineRejectsUnsafeStart() => Check(Select(ShapeType.Line,5,5,20,5).Length==0,"unsafe start was yielded");
    private static void LineStopsAtMargin() => EqualPoints(Select(ShapeType.Line,244,20,250,20),new Point(244,20),new Point(245,20));
    private static void EveryShapeRejectsUnsafeStart()
    {
        foreach (ShapeType shape in Enum.GetValues<ShapeType>())
            Check(Select(shape,5,5,20,20).Length==0,$"{shape} accepted unsafe start");
    }
    private static void CornerVerticalFirst() => EqualPoints(Select(ShapeType.Corner,20,20,22,22),new Point(20,20),new Point(20,21),new Point(20,22),new Point(21,22),new Point(22,22));
    private static void CornerHorizontalFirst() => EqualPoints(Select(ShapeType.Corner,20,20,22,22,true),new Point(20,20),new Point(21,20),new Point(22,20),new Point(22,21),new Point(22,22));
    private static void CornerSharedOnce(){Point[] p=Select(ShapeType.Corner,20,20,22,22);Check(p.Length==p.Distinct().Count(),"corner duplicated its shared vertex");}
    private static void CornerClippingStops() => EqualPoints(Select(ShapeType.Corner,245,20,250,25,true),new Point(245,20));

    private static void FilledSquareLimit(){Point[] p=Select(ShapeType.SquareFilled,50,50,200,200);Check(p.Length==3600&&p.Max(x=>x.X)-p.Min(x=>x.X)==59&&p.Max(x=>x.Y)-p.Min(x=>x.Y)==59,"filled square limit");}
    private static void OutlineSquareLimit(){Point[] p=Select(ShapeType.SquareEmpty,50,50,230,230);Check(p.Length==636&&p.Max(x=>x.X)-p.Min(x=>x.X)==159,"outline square limit");}
    private static void DegenerateSquareUnique(){Point[] p=Select(ShapeType.SquareEmpty,20,20,20,24);Check(p.Length==5&&p.Distinct().Count()==5,"degenerate outline duplicated tiles");}
    private static void SquareClipsWorld(){Point[] p=Select(ShapeType.SquareFilled,244,244,255,255);Check(p.Length==4&&p.All(x=>WorldGen.InWorld(x.X,x.Y,10)),"square yielded unsafe border tiles");}

    private static void FilledCircleUnique(){Point[] p=Select(ShapeType.CircleFilled,30,30,35,30);Check(p.Length>0&&p.Length==p.Distinct().Count()&&p.Contains(new Point(30,30)),"filled circle invalid");}
    private static void ThinCircleBoundary(){var filled=Select(ShapeType.CircleFilled,30,30,35,30).ToHashSet();Point[] edge=Select(ShapeType.CircleEmpty,30,30,35,30);Check(edge.Length>0&&edge.All(filled.Contains)&&!edge.Contains(new Point(30,30)),"thin circle contains interior/non-circle tile");}
    private static void ConnectedCircleBoundary(){Point[] thin=Select(ShapeType.CircleEmpty,30,30,35,30);Point[] connected=Select(ShapeType.CircleEmpty,30,30,35,30,true);Check(connected.Length>0&&connected.Length<=thin.Length,"connected outline boundary policy changed");}
    private static void CircleRadiusCaps(){int a=Select(ShapeType.CircleFilled,120,120,220,120).Length,b=Select(ShapeType.CircleFilled,120,120,245,120).Length;int c=Select(ShapeType.CircleEmpty,120,120,220,120).Length,d=Select(ShapeType.CircleEmpty,120,120,245,120).Length;Check(a==b&&c==d,"circle radius cap not stable");}
    private static void CircleClipsWorld(){Point[] p=Select(ShapeType.CircleFilled,244,244,250,244);Check(p.Length>0&&p.All(x=>WorldGen.InWorld(x.X,x.Y,10)),"circle yielded unsafe border tile");}

    private static void SuccessfulPlaceConsumesOnce(){Item item=Solid(stack:3);Player p=PlayerWith(item);var r=Operate(p);Check(r.sound&&item.stack==2&&r.consumed.GetValueOrDefault(100)==1,"successful place consumption");}
    private static void NonConsumableNotReported(){Item item=Solid(stack:1,consumable:false);Player p=PlayerWith(item);var r=Operate(p);Check(r.sound&&item.stack==1&&r.consumed.Count==0,"nonconsumable material was reported");}
    private static void ConsumptionHookVetoPlacement(){Item item=Solid(stack:3);Player p=PlayerWith(item);ItemLoader.ConsumeAllowed=false;var r=Operate(p);Check(r.sound&&Main.tile[20,20].HasTile&&Main.tile[20,20].TileType==100&&item.stack==3&&r.consumed.Count==0,"consumption veto incorrectly cancelled placement or reported resource");}
    private static void TileWandConsumesAmmo(){Item wand=Solid(type:100,stack:1,consumable:false);wand.tileWand=101;Item ammo=new(){type=101,stack=3};Player p=PlayerWith(wand);p.inventory[1]=ammo;var r=Operate(p);Check(wand.stack==1&&ammo.stack==2&&r.consumed.GetValueOrDefault(101)==1,"tile wand consumed wrong item");}
    private static void TileWandAmmoVetoPlacement(){Item wand=Solid(type:100,stack:1,consumable:false);wand.tileWand=101;Item ammo=new(){type=101,stack=3};Player p=PlayerWith(wand);p.inventory[1]=ammo;ItemLoader.ConsumeAllowed=false;var r=Operate(p);Check(r.sound&&Main.tile[20,20].HasTile&&wand.stack==1&&ammo.stack==3&&r.consumed.Count==0,"ammo consumption veto incorrectly cancelled tile-wand placement");}
    private static void MissingTileWandAmmoAtomic(){Item wand=Solid(type:100,stack:1,consumable:false);wand.tileWand=101;Player p=PlayerWith(wand);var r=Operate(p);Check(!r.sound&&WorldGen.Calls.Count==0&&wand.stack==1,"missing ammo mutated state");}
    private static void LoaderRejectionAtomic(){Item item=Solid(stack:3);Player p=PlayerWith(item);TileLoader.Allowed=false;var r=Operate(p);Check(!r.sound&&item.stack==3&&r.consumed.Count==0&&WorldGen.Calls.All(x=>x.StartsWith("can-place")),"loader rejection not atomic");}
    private static void FailedNewTilePlaceAtomic(){Item item=Solid(stack:3);Player p=PlayerWith(item);WorldGen.PlaceAllowed=false;var r=Operate(p);Check(!r.sound&&item.stack==3&&r.consumed.Count==0&&!Main.tile[20,20].HasTile,"failed placement consumed or changed state");}
    private static void MatchingTileReshapes(){Item item=Solid(stack:3);Player p=PlayerWith(item);Main.tile[20,20].HasTile=true;Main.tile[20,20].TileType=100;var r=Operate(p,block:BlockType.HalfBlock);Check(!r.sound&&item.stack==3&&r.consumed.Count==0&&Main.tile[20,20].BlockType==BlockType.HalfBlock,"matching tile transaction");}
    private static void DisabledReplacementAtomic(){Item item=Solid(stack:3);Player p=PlayerWith(item);p.TileReplacementEnabled=false;Main.tile[20,20].HasTile=true;Main.tile[20,20].TileType=110;Main.tile[20,20].BlockType=BlockType.SlopeDownLeft;var r=Operate(p);Check(!r.sound&&item.stack==3&&Main.tile[20,20].TileType==110&&Main.tile[20,20].BlockType==BlockType.SlopeDownLeft,"disabled replacement mutated tile");}
    private static void RopeCannotReplacePlatform(){Main.tileRope[120]=true;TileID.Sets.Platforms[110]=true;Item rope=new(){type=120,stack=3,createTile=120};Player p=PlayerWith(rope);Main.tile[20,20].HasTile=true;Main.tile[20,20].TileType=110;var r=Operate(p,place:PlaceType.Rope);Check(!r.sound&&rope.stack==3&&Main.tile[20,20].TileType==110,"rope replaced platform");}
    private static void InsufficientPickAtomic(){Item item=Solid(stack:3);Player p=PlayerWith(item);p.CanPick=false;Main.tile[20,20].HasTile=true;Main.tile[20,20].TileType=110;Main.tile[20,20].BlockType=BlockType.SlopeUpLeft;var r=Operate(p);Check(!r.sound&&item.stack==3&&Main.tile[20,20].BlockType==BlockType.SlopeUpLeft,"failed pick mutated slope");}
    private static void SuccessfulReplacementConsumes(){Item item=Solid(stack:3);Player p=PlayerWith(item);Main.tile[20,20].HasTile=true;Main.tile[20,20].TileType=110;var r=Operate(p);Check(r.sound&&item.stack==2&&Main.tile[20,20].TileType==100&&r.consumed[100]==1,"replacement transaction");}
    private static void ReplaceFallback(){Item item=Solid(stack:3);Player p=PlayerWith(item);Main.tile[20,20].HasTile=true;Main.tile[20,20].TileType=110;WorldGen.ReplaceAllowed=false;var r=Operate(p);Check(r.sound&&item.stack==2&&WorldGen.Calls.FindIndex(x=>x.StartsWith("kill"))<WorldGen.Calls.FindIndex(x=>x.StartsWith("place"))&&r.consumed[100]==1,"replacement fallback");}
    private static void FailedReplaceFallbackRestores(){Item item=Solid(stack:3);Player p=PlayerWith(item);Main.tile[20,20].HasTile=true;Main.tile[20,20].TileType=110;Main.tile[20,20].BlockType=BlockType.SlopeDownLeft;WorldGen.ReplaceAllowed=false;WorldGen.PlaceAllowed=false;var r=Operate(p);Check(!r.sound&&item.stack==3&&r.consumed.Count==0&&Main.tile[20,20].HasTile&&Main.tile[20,20].TileType==110&&Main.tile[20,20].BlockType==BlockType.SlopeDownLeft,"failed fallback did not restore old tile");}
    private static void SolidResetsExternalBelow(){Item item=Solid(stack:3);Player p=PlayerWith(item);Main.tile[20,21].BlockType=BlockType.SlopeDownLeft;Operate(p,selected:new HashSet<Point>{new(20,20)});Check(Main.tile[20,21].BlockType==BlockType.Solid,"external below slope not reset");}
    private static void SolidPreservesSelectedBelow(){Item item=Solid(stack:3);Player p=PlayerWith(item);Main.tile[20,21].BlockType=BlockType.SlopeDownLeft;Operate(p,selected:new HashSet<Point>{new(20,20),new(20,21)});Check(Main.tile[20,21].BlockType==BlockType.SlopeDownLeft,"selected below slope was reset");}
    private static void UnsafeOperationStopsEarly(){Item item=Solid(stack:3);Player p=PlayerWith(item);var r=Operate(p,5,5);Check(!r.sound&&item.stack==3&&WorldGen.Calls.Count==0,"unsafe operation reached loader/world");}

    private static void ConfigurePacketPlayer(int stack=50)
    {
        Player player=Main.player[1];
        player.inventory[0]=new Item{type=900,stack=1,consumable=false,ModItem=new SpaceWand()};
        player.inventory[1]=Solid(stack:stack);
        player.selectedItem=0;
        Main.netMode=NetmodeID.Server;
    }
    private static void PacketRequiresServer(){ConfigurePacketPlayer();Main.netMode=NetmodeID.MultiplayerClient;Packet(ShapeType.Line,20,20,22,20).Receive();Check(WorldGen.Calls.Count==0,"client executed receive");}
    private static void PacketRejectsSender(){ConfigurePacketPlayer();SpaceWandOperation p=Packet(ShapeType.Line);p.Sender=99;p.Receive();Check(WorldGen.Calls.Count==0,"invalid sender executed");}
    private static void PacketRejectsInactive(){ConfigurePacketPlayer();Main.player[1].active=false;Packet(ShapeType.Line).Receive();Check(WorldGen.Calls.Count==0,"inactive sender executed");}
    private static void PacketRejectsEnums(){ConfigurePacketPlayer();Packet((ShapeType)255).Receive();Packet(ShapeType.Line,place:(PlaceType)255).Receive();Packet(ShapeType.Line,block:(BlockType)255).Receive();Check(WorldGen.Calls.Count==0,"invalid enum executed");}
    private static void PacketRejectsNonFinite(){ConfigurePacketPlayer();SpaceWandOperation a=SpaceWandOperation.Get(new Vector2(float.NaN,0),Pixel(20,20),ShapeType.Line,BlockType.Solid,PlaceType.Soild,false);a.Sender=1;a.Receive();SpaceWandOperation b=SpaceWandOperation.Get(Pixel(20,20),new Vector2(float.PositiveInfinity,0),ShapeType.Line,BlockType.Solid,PlaceType.Soild,false);b.Sender=1;b.Receive();Check(WorldGen.Calls.Count==0,"nonfinite packet executed");}
    private static void PacketBottomToTop(){ConfigurePacketPlayer();Packet(ShapeType.SquareFilled,20,20,21,22).Receive();int[] ys=WorldGen.Calls.Where(x=>x.StartsWith("place:")).Select(x=>int.Parse(x.Split(',')[1])).ToArray();Check(ys.SequenceEqual(ys.OrderByDescending(x=>x)),"packet did not operate bottom-to-top");}
    private static void OutlineSyncCoverage(){ConfigurePacketPlayer();Packet(ShapeType.Line,20,20,22,20).Receive();Check(NetMessage.Sent.Count==3&&NetMessage.Sent.All(x=>x.Width==3&&x.Height==3),"outline sync coverage");}
    private static void FilledSyncCoverage(){ConfigurePacketPlayer();Packet(ShapeType.SquareFilled,20,20,21,22).Receive();Check(NetMessage.Sent.SequenceEqual(new[]{new NetMessage.Sync(19,19,4,5)}),"filled bounding sync");}
    private static void PacketReportsConsumption(){ConfigurePacketPlayer();Packet(ShapeType.Line,20,20,22,20).Receive();Check(ConsumeItemPacket.Sent.Count==1&&ConsumeItemPacket.Sent[0].Sender==1&&ConsumeItemPacket.Sent[0].Items.GetValueOrDefault(100)==3,"packet consumption aggregation");}
    private static void PacketOneSound(){ConfigurePacketPlayer();Packet(ShapeType.Line,20,20,22,20).Receive();Check(PlaySoundPacket.Sent.Count==1,"packet sound count");}
    private static void PacketNoChangeNoPackets(){ConfigurePacketPlayer();TileLoader.Allowed=false;Packet(ShapeType.Line,20,20,22,20).Receive();Check(NetMessage.Sent.Count==0&&ConsumeItemPacket.Sent.Count==0&&PlaySoundPacket.Sent.Count==0,"unchanged packet emitted side effects");}
    private static void FailedReplaceFallbackNoPackets(){ConfigurePacketPlayer();Main.tile[20,20].HasTile=true;Main.tile[20,20].TileType=110;WorldGen.ReplaceAllowed=false;WorldGen.PlaceAllowed=false;Packet(ShapeType.Line).Receive();Check(Main.tile[20,20].HasTile&&Main.tile[20,20].TileType==110&&Main.player[1].inventory[1].stack==50&&NetMessage.Sent.Count==0&&ConsumeItemPacket.Sent.Count==0&&PlaySoundPacket.Sent.Count==0,"failed fallback changed terrain or sent a packet");}
    private static void PacketConsumptionVeto(){ConfigurePacketPlayer();ItemLoader.ConsumeAllowed=false;Packet(ShapeType.Line).Receive();Check(Main.tile[20,20].HasTile&&Main.player[1].inventory[1].stack==50&&NetMessage.Sent.Count==1&&ConsumeItemPacket.Sent.Count==0&&PlaySoundPacket.Sent.Count==1,"consumption veto suppressed valid tile sync/sound or reported an item");}

    private static void ShapeMethodsRejectNonFinite()
    {
        Vector2 good=Pixel(20,20),bad=new(float.NaN,float.PositiveInfinity);
        Check(!SpaceWand.GetLineTiles(good,bad).Any(),"line accepted non-finite endpoint");
        Check(SpaceWand.GetCornerTiles(good,bad,false).Count==0,"corner accepted non-finite endpoint");
        Check(!SpaceWand.GetSquareTiles(good,bad,true).Any(),"square accepted non-finite endpoint");
        Check(!SpaceWand.GetCircleTiles(good,bad,true,false).Any(),"circle accepted non-finite endpoint");
    }

    private static void ExtremeFiniteLine()
    {
        Point[] points=SpaceWand.GetLineTiles(Pixel(20,20),new Vector2(float.MaxValue,20*16f)).ToArray();
        Check(points.Length==226&&points[0].Equals(new Point(20,20))&&points[^1].Equals(new Point(245,20)),"extreme line overflowed or reversed direction");
    }

    private static void ExtremeFiniteCorner()
    {
        Point[] points=SpaceWand.GetCornerTiles(Pixel(20,20),new Vector2(float.MaxValue,float.MaxValue),true).ToArray();
        Check(points.Length==226&&points[0].Equals(new Point(20,20))&&points[^1].Equals(new Point(245,20)),"extreme corner overflowed or resumed after clipping");
    }

    private static void ExtremeFiniteSquare()
    {
        Point[] points=SpaceWand.GetSquareTiles(Pixel(20,20),new Vector2(float.MaxValue,float.MaxValue),true).ToArray();
        Check(points.Length==3600&&points.Min(p=>p.X)==20&&points.Max(p=>p.X)==79&&points.Min(p=>p.Y)==20&&points.Max(p=>p.Y)==79,"extreme square lost drag quadrant or size cap");
    }

    private static void FailedEmptyPlaceRestoresPartialMutation()
    {
        Item item=Solid(stack:3);Player player=PlayerWith(item);Tile tile=Main.tile[20,20];tile.TileType=77;tile.BlockType=BlockType.SlopeDownLeft;
        WorldGen.PlaceAllowed=false;WorldGen.MutateBeforePlaceFailure=true;var result=Operate(player);
        Check(!result.sound&&!tile.HasTile&&tile.TileType==77&&tile.BlockType==BlockType.SlopeDownLeft&&item.stack==3&&result.consumed.Count==0,"failed empty placement leaked a partial tile mutation");
    }

    private static void FailedGrassPlaceRestoresPartialMutation()
    {
        Item seed=new(){type=200,stack=3,createTile=TileID.Grass};Player player=PlayerWith(seed);Tile tile=Main.tile[20,20];tile.TileType=77;tile.BlockType=BlockType.SlopeUpRight;
        WorldGen.PlaceAllowed=false;WorldGen.MutateBeforePlaceFailure=true;var result=Operate(player,place:PlaceType.GrassSeed);
        Check(!result.sound&&!tile.HasTile&&tile.TileType==77&&tile.BlockType==BlockType.SlopeUpRight&&seed.stack==3&&result.consumed.Count==0,"failed grass placement leaked a partial tile mutation");
    }

    private static void FailedReplaceRestoresBeforeFallback()
    {
        Item item=Solid(stack:3);Player player=PlayerWith(item);Main.tile[20,20].HasTile=true;Main.tile[20,20].TileType=110;Main.tile[20,20].BlockType=BlockType.SlopeDownLeft;
        WorldGen.ReplaceAllowed=false;WorldGen.MutateBeforeReplaceFailure=true;var result=Operate(player);
        Check(result.sound&&WorldGen.KillObservedTypes.SequenceEqual(new ushort[]{110})&&Main.tile[20,20].TileType==100&&item.stack==2&&result.consumed.GetValueOrDefault(100)==1,"fallback observed the failed replacement's partial state");
    }

    private static void ForbiddenReplacementPreservesBlockShape()
    {
        Item item=Solid(stack:3);Player player=PlayerWith(item);Tile tile=Main.tile[20,20];tile.HasTile=true;tile.TileType=110;tile.BlockType=BlockType.SlopeDownLeft;
        ImproveGame.Helpers.ProjectionHelpers.ValidReplacementAllowed=false;var result=Operate(player,block:BlockType.HalfBlock);
        Check(!result.sound&&tile.TileType==110&&tile.BlockType==BlockType.SlopeDownLeft&&item.stack==3&&result.consumed.Count==0,"forbidden replacement reshaped the existing tile");
    }

    private static void MatchingTileRequiresPoundPermission()
    {
        Item item=Solid(stack:3);Player player=PlayerWith(item);Tile tile=Main.tile[20,20];tile.HasTile=true;tile.TileType=100;tile.BlockType=BlockType.SlopeDownLeft;
        WorldGen.CanPoundAllowed=false;var result=Operate(player,block:BlockType.HalfBlock);
        Check(!result.sound&&tile.BlockType==BlockType.SlopeDownLeft&&item.stack==3&&result.consumed.Count==0,"matching tile bypassed pound permission");
    }

    private static void PacketSyncsSlopeOnlyChange()
    {
        ConfigurePacketPlayer();Tile tile=Main.tile[20,20];tile.HasTile=true;tile.TileType=100;tile.BlockType=BlockType.SlopeDownLeft;
        Packet(ShapeType.Line,block:BlockType.HalfBlock).Receive();
        Check(tile.BlockType==BlockType.HalfBlock&&NetMessage.Sent.SequenceEqual(new[]{new NetMessage.Sync(19,19,3,3)})&&ConsumeItemPacket.Sent.Count==0&&PlaySoundPacket.Sent.Count==0,"slope-only mutation was not synchronized silently");
    }

    private static void PacketSyncsExternalSupportChange()
    {
        ConfigurePacketPlayer();Tile tile=Main.tile[20,20];tile.HasTile=true;tile.TileType=100;tile.BlockType=BlockType.Solid;Main.tile[20,21].BlockType=BlockType.SlopeDownLeft;
        Packet(ShapeType.Line).Receive();
        Check(Main.tile[20,21].BlockType==BlockType.Solid&&NetMessage.Sent.SequenceEqual(new[]{new NetMessage.Sync(19,20,3,3)})&&ConsumeItemPacket.Sent.Count==0&&PlaySoundPacket.Sent.Count==0,"external support mutation was omitted or treated as a placement");
    }

    private static void OutlinePacketSyncsOnlyChangedTiles()
    {
        ConfigurePacketPlayer();foreach(int x in new[]{20,22}){Main.tile[x,20].HasTile=true;Main.tile[x,20].TileType=100;}
        Packet(ShapeType.Line,20,20,22,20).Receive();
        Check(NetMessage.Sent.SequenceEqual(new[]{new NetMessage.Sync(20,19,3,3)})&&ConsumeItemPacket.Sent.Single().Items.GetValueOrDefault(100)==1&&PlaySoundPacket.Sent.Count==1,"outline synchronized selected no-ops instead of its dirty tile");
    }

    private static void FilledPacketBoundsOnlyChangedTiles()
    {
        ConfigurePacketPlayer();
        for(int x=20;x<=22;x++)for(int y=20;y<=21;y++){Main.tile[x,y].HasTile=true;Main.tile[x,y].TileType=100;}
        Main.tile[20,20].HasTile=false;Main.tile[22,21].HasTile=false;
        Packet(ShapeType.SquareFilled,20,20,22,21).Receive();
        Check(NetMessage.Sent.SequenceEqual(new[]{new NetMessage.Sync(19,19,5,4)})&&ConsumeItemPacket.Sent.Single().Items.GetValueOrDefault(100)==2&&PlaySoundPacket.Sent.Count==1,"filled sync bounds did not follow committed dirty tiles");
    }

    private static void FailedPartialMutationNoPackets()
    {
        ConfigurePacketPlayer();WorldGen.PlaceAllowed=false;WorldGen.MutateBeforePlaceFailure=true;Packet(ShapeType.Line).Receive();
        Check(!Main.tile[20,20].HasTile&&Main.player[1].inventory[1].stack==50&&NetMessage.Sent.Count==0&&ConsumeItemPacket.Sent.Count==0&&PlaySoundPacket.Sent.Count==0,"restored partial failure emitted authority side effects");
    }

    private static void InventoryExhaustionSyncsCommittedTiles()
    {
        ConfigurePacketPlayer(stack:2);Packet(ShapeType.Line,20,20,23,20).Receive();
        Check(Main.tile[20,20].HasTile&&Main.tile[21,20].HasTile&&!Main.tile[22,20].HasTile&&!Main.tile[23,20].HasTile&&NetMessage.Sent.Count==2&&ConsumeItemPacket.Sent.Single().Items.GetValueOrDefault(100)==2&&PlaySoundPacket.Sent.Count==1,"inventory exhaustion did not stop and synchronize the committed prefix");
    }

    private static void OutlineDirtySyncOrder()
    {
        ConfigurePacketPlayer();Packet(ShapeType.Line,20,20,22,20).Receive();
        Check(NetMessage.Sent.SequenceEqual(new[]{new NetMessage.Sync(19,19,3,3),new NetMessage.Sync(20,19,3,3),new NetMessage.Sync(21,19,3,3)}),"outline dirty synchronization order was nondeterministic");
    }

    private static void FalsePlaceWithCommittedPostcondition()
    {
        Item item=Solid(stack:3);Player player=PlayerWith(item);WorldGen.PlaceAllowed=false;WorldGen.CommitBeforePlaceFailure=true;
        var result=Operate(player);
        Check(result.sound&&Main.tile[20,20].HasTile&&Main.tile[20,20].TileType==100&&item.stack==2&&result.consumed.GetValueOrDefault(100)==1,"a committed placement was rejected because of its unreliable false return");
    }

    private static void TruePlaceWithoutCommittedPostcondition()
    {
        Item item=Solid(stack:3);Player player=PlayerWith(item);WorldGen.ReportPlaceSuccessWithoutMutation=true;
        var result=Operate(player);
        Check(!result.sound&&!Main.tile[20,20].HasTile&&item.stack==3&&result.consumed.Count==0,"a true return without the requested tile was treated as a commit");
    }

    private static void FalseGrassPlaceWithCommittedPostcondition()
    {
        Item seed=new(){type=200,stack=3,createTile=TileID.Grass};Player player=PlayerWith(seed);
        WorldGen.PlaceAllowed=false;WorldGen.CommitBeforePlaceFailure=true;var result=Operate(player,place:PlaceType.GrassSeed);
        Check(result.sound&&Main.tile[20,20].HasTile&&Main.tile[20,20].TileType==TileID.Grass&&seed.stack==2&&result.consumed.GetValueOrDefault(200)==1,"a committed grass placement was rejected because of its false return");
    }

    private static void FalseReplaceWithCommittedPostcondition()
    {
        Item item=Solid(stack:3);Player player=PlayerWith(item);Tile tile=Main.tile[20,20];tile.HasTile=true;tile.TileType=110;
        WorldGen.ReplaceAllowed=false;WorldGen.CommitBeforeReplaceFailure=true;var result=Operate(player);
        Check(result.sound&&tile.TileType==100&&item.stack==2&&result.consumed.GetValueOrDefault(100)==1&&WorldGen.KillObservedTypes.Count==0,"a committed replacement fell through to destructive fallback");
    }

    private static void TrueReplaceWithoutCommittedPostcondition()
    {
        Item item=Solid(stack:3);Player player=PlayerWith(item);Tile tile=Main.tile[20,20];tile.HasTile=true;tile.TileType=110;tile.TileFrameX=12;
        WorldGen.ReportReplaceSuccessWithoutMutation=true;var result=Operate(player);
        int replace=WorldGen.Calls.FindIndex(x=>x.StartsWith("replace"));int kill=WorldGen.Calls.FindIndex(x=>x.StartsWith("kill"));int place=WorldGen.Calls.FindIndex(x=>x.StartsWith("place"));
        Check(result.sound&&tile.TileType==100&&item.stack==2&&result.consumed.GetValueOrDefault(100)==1&&replace>=0&&replace<kill&&kill<place&&WorldGen.KillObservedTypes.SequenceEqual(new ushort[]{110}),"a true replacement without its postcondition skipped the clean fallback");
    }

    private static void LoaderRejectionRestoresFullNeighborhood()
    {
        Item item=Solid(stack:3);Player player=PlayerWith(item);Tile target=Main.tile[20,20];target.HasTile=true;target.TileType=77;target.BlockType=BlockType.SlopeDownLeft;target.TileFrameX=8;target.TileFrameY=9;target.TileColor=3;target.IsActuated=true;
        Tile neighbor=Main.tile[21,20];neighbor.TileFrameX=14;neighbor.TileColor=5;
        ObservedTileState targetBefore=ObservedTileState.Capture(target),neighborBefore=ObservedTileState.Capture(neighbor);
        TileLoader.Allowed=false;TileLoader.MutateBeforeReject=true;var result=Operate(player);
        Check(!result.sound&&ObservedTileState.Capture(target)==targetBefore&&ObservedTileState.Capture(neighbor)==neighborBefore&&item.stack==3&&result.consumed.Count==0,"CanPlace rejection leaked full-state or neighbor mutations");
    }

    private static void FailedPlaceRestoresFullNeighborhood()
    {
        Item item=Solid(stack:3);Player player=PlayerWith(item);Tile target=Main.tile[20,20];target.TileType=77;target.BlockType=BlockType.SlopeUpLeft;target.TileFrameX=8;target.TileFrameY=9;target.TileColor=3;target.IsActuated=true;
        Tile neighbor=Main.tile[21,20];neighbor.TileFrameX=14;neighbor.TileColor=5;neighbor.IsActuated=true;
        ObservedTileState targetBefore=ObservedTileState.Capture(target),neighborBefore=ObservedTileState.Capture(neighbor);
        WorldGen.PlaceAllowed=false;WorldGen.MutateBeforePlaceFailure=true;WorldGen.MutateRightNeighborOnPlace=true;var result=Operate(player);
        Check(!result.sound&&ObservedTileState.Capture(target)==targetBefore&&ObservedTileState.Capture(neighbor)==neighborBefore&&item.stack==3&&result.consumed.Count==0,"failed placement leaked extended target or neighboring metadata");
    }

    private static void FailedFallbackRestoresFullNeighborhood()
    {
        Item item=Solid(stack:3);Player player=PlayerWith(item);Tile target=Main.tile[20,20];target.HasTile=true;target.TileType=110;target.BlockType=BlockType.SlopeDownRight;target.TileFrameX=8;target.TileFrameY=9;target.TileColor=3;target.IsActuated=true;
        Tile neighbor=Main.tile[21,20];neighbor.TileFrameX=14;neighbor.TileColor=5;neighbor.IsActuated=true;
        ObservedTileState targetBefore=ObservedTileState.Capture(target),neighborBefore=ObservedTileState.Capture(neighbor);
        WorldGen.ReplaceAllowed=false;WorldGen.MutateBeforeReplaceFailure=true;WorldGen.PlaceAllowed=false;WorldGen.MutateBeforePlaceFailure=true;WorldGen.MutateRightNeighborOnPlace=true;var result=Operate(player);
        Check(!result.sound&&ObservedTileState.Capture(target)==targetBefore&&ObservedTileState.Capture(neighbor)==neighborBefore&&item.stack==3&&result.consumed.Count==0,"failed replacement fallback did not restore its full neighborhood");
    }

    private static void PacketRequiresHeldSpaceWand()
    {
        ConfigurePacketPlayer();Main.player[1].HeldItem.ModItem=null;Packet(ShapeType.Line).Receive();
        Check(WorldGen.Calls.Count==0&&Main.player[1].inventory[1].stack==50&&NetMessage.Sent.Count==0&&ConsumeItemPacket.Sent.Count==0&&PlaySoundPacket.Sent.Count==0,"a sender not holding Space Wand executed an authoritative request");
    }

    private static void PacketRejectsBuildingDisabledSender()
    {
        ConfigurePacketPlayer();Main.player[1].noBuilding=true;Packet(ShapeType.Line).Receive();
        Check(WorldGen.Calls.Count==0&&Main.player[1].inventory[1].stack==50&&NetMessage.Sent.Count==0,"a building-disabled sender executed a request");
    }

    private static void PacketRejectsDeadSender()
    {
        ConfigurePacketPlayer();Main.player[1].dead=true;Packet(ShapeType.Line).Receive();
        Check(WorldGen.Calls.Count==0&&Main.player[1].inventory[1].stack==50&&NetMessage.Sent.Count==0,"a dead sender executed a request");
    }

    private static void PacketSyncsFrameOnlyMutation()
    {
        ConfigurePacketPlayer();Tile tile=Main.tile[20,20];tile.HasTile=true;tile.TileType=100;tile.BlockType=BlockType.Solid;tile.TileFrameX=4;WorldGen.MutateFrameOnFrame=true;
        Packet(ShapeType.Line).Receive();
        Check(tile.TileFrameX==5&&NetMessage.Sent.SequenceEqual(new[]{new NetMessage.Sync(19,19,3,3)})&&ConsumeItemPacket.Sent.Count==0&&PlaySoundPacket.Sent.Count==0,"frame-only committed mutation was omitted or misclassified");
    }

    private static void OutlinePacketSyncsCommittedNeighborMutation()
    {
        ConfigurePacketPlayer();WorldGen.MutateRightNeighborOnPlace=true;Packet(ShapeType.Line).Receive();
        Check(Main.tile[21,20].TileFrameX==1&&NetMessage.Sent.SequenceEqual(new[]{new NetMessage.Sync(19,19,3,3),new NetMessage.Sync(20,19,3,3)})&&ConsumeItemPacket.Sent.Single().Items.GetValueOrDefault(100)==1&&PlaySoundPacket.Sent.Count==1,"outline sync omitted a committed engine neighbor mutation");
    }

    private static void FailedNeighborMutationNoPackets()
    {
        ConfigurePacketPlayer();WorldGen.PlaceAllowed=false;WorldGen.MutateBeforePlaceFailure=true;WorldGen.MutateRightNeighborOnPlace=true;Packet(ShapeType.Line).Receive();
        Check(!Main.tile[20,20].HasTile&&Main.tile[21,20].TileFrameX==0&&Main.tile[21,20].TileColor==0&&!Main.tile[21,20].IsActuated&&Main.player[1].inventory[1].stack==50&&NetMessage.Sent.Count==0&&ConsumeItemPacket.Sent.Count==0&&PlaySoundPacket.Sent.Count==0,"rolled-back neighbor mutation survived or synchronized");
    }

    private static void FilledPacketBoundsCommittedNeighborMutation()
    {
        ConfigurePacketPlayer();WorldGen.MutateRightNeighborOnPlace=true;Packet(ShapeType.SquareFilled).Receive();
        Check(NetMessage.Sent.SequenceEqual(new[]{new NetMessage.Sync(19,19,4,3)})&&ConsumeItemPacket.Sent.Single().Items.GetValueOrDefault(100)==1&&PlaySoundPacket.Sent.Count==1,"filled dirty bounds excluded a committed mutation outside the selected set");
    }
}

internal static class EntryPoint
{
    public static int Main(string[] args) => ContractProgram.Run(args);
}
