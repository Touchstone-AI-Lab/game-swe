using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Aequus;
using Aequus.Common.Carpentry;
using Aequus.Common.Carpentry.Results;
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader.IO;

internal static class ContractProgram
{
    private static readonly Dictionary<string,Action> Cases=new()
    {
        ["completion_trim_is_stable_and_unique"]=CompletionTrim,
        ["completion_add_is_idempotent"]=CompletionAdd,
        ["save_uses_independent_list"]=SaveCopies,
        ["load_clears_stale_and_deduplicates"]=LoadCanonical,
        ["unknown_names_survive_local_persistence"]=UnknownPersists,
        ["completion_frame_uses_global_ids"]=CompletionGlobalIds,
        ["completion_frame_is_unique_and_sorted"]=CompletionSorted,
        ["unknown_names_are_omitted_only_from_wire"]=UnknownOmittedWire,
        ["completion_receive_replaces_on_success"]=CompletionReceive,
        ["completion_receive_rejects_negative_count"]=CompletionNegative,
        ["completion_receive_rejects_large_count"]=CompletionLarge,
        ["completion_receive_rejects_duplicate_ids"]=CompletionDuplicate,
        ["completion_receive_rejects_out_of_range_id"]=CompletionRange,
        ["completion_receive_truncation_rolls_back"]=CompletionTruncated,
        ["completion_receive_rejects_unsorted_ids"]=CompletionUnsorted,
        ["building_load_continues_after_missing_key"]=BuildingLoadContinue,
        ["building_load_clears_stale_state"]=BuildingLoadClears,
        ["building_load_copies_tag_lists"]=BuildingLoadCopies,
        ["world_save_does_not_clear_live_buildings"]=WorldSavePreserves,
        ["world_save_load_restores_completions_and_buildings"]=WorldSaveLoadBoth,
        ["clear_world_clears_both_stores"]=ClearWorldBoth,
        ["building_save_skips_unknown_and_invalid_state"]=BuildingSaveFilters,
        ["building_load_filters_overflowing_rectangles"]=BuildingLoadFiltersOverflow,
        ["trim_checks_every_step_without_stalling"]=TrimEveryStep,
        ["trim_removes_failed_location_and_keeps_later"]=TrimFailContinues,
        ["trim_removes_throwing_location_and_keeps_later"]=TrimExceptionContinues,
        ["add_rejects_unknown_challenge_id"]=AddUnknown,
        ["add_rejects_nonpositive_rectangle"]=AddBadRectangle,
        ["add_rejects_overlapping_rectangle"]=AddOverlap,
        ["add_rejects_overflowing_rectangle"]=AddOverflow,
        ["building_frame_orders_groups"]=BuildingSendSorted,
        ["building_frame_count_matches_nonempty_groups"]=BuildingSendCount,
        ["building_frame_skips_empty_groups"]=BuildingSkipEmpty,
        ["building_receive_replaces_on_success"]=BuildingReceive,
        ["building_receive_rejects_negative_group_count"]=BuildingNegative,
        ["building_receive_rejects_duplicate_group"]=BuildingDuplicate,
        ["building_receive_rejects_unknown_group"]=BuildingUnknown,
        ["building_receive_rejects_excessive_locations"]=BuildingLarge,
        ["building_receive_rejects_empty_group"]=BuildingEmpty,
        ["building_receive_rejects_invalid_rectangle"]=BuildingBadRect,
        ["building_receive_rejects_overlap"]=BuildingOverlap,
        ["building_receive_truncation_rolls_back"]=BuildingTruncated,
        ["building_receive_rejects_unsorted_groups"]=BuildingUnsorted,
        ["building_receive_rejects_overflowing_rectangle"]=BuildingOverflow,
        ["world_sync_writes_completions_then_buildings"]=WorldSyncOrder,
        ["world_sync_rolls_back_both_sections"]=WorldSyncRollback,
        ["client_completion_requests_without_local_mutation"]=ClientComplete,
        ["server_completion_adds_and_broadcasts_once"]=ServerComplete,
        ["server_reset_clears_then_broadcasts"]=ServerReset,
        ["building_add_packet_requires_real_change"]=AddPacketOnChange,
        ["quiet_building_change_never_echoes"]=QuietNoEcho,
        ["building_remove_packet_requires_real_change"]=RemovePacketOnChange,
        ["player_clone_copies_independent_completion_list"]=PlayerClone,
        ["client_state_copy_is_independent"]=ClientCopy,
        ["invalid_selected_bounty_is_not_saved"]=InvalidSelectedBounty,
        ["building_buff_includes_challenge_zero"]=BuffChallengeZero,
        ["building_buff_applies_once_per_group"]=BuffOncePerGroup,
        ["building_buff_ignores_nonintersecting_and_nonpositive"]=BuffIgnoresInapplicable,
        ["building_buff_ignores_stale_or_null_groups"]=BuffIgnoresStale,
        ["post_update_requires_owner_tenth_safe_tick"]=PostUpdateGate,
        ["completion_load_rejects_wrong_tag_type"]=CompletionLoadWrongType,
        ["completion_send_rejects_invalid_registry_without_writing"]=CompletionSendInvalidRegistry,
        ["completion_receive_registry_change_rolls_back"]=CompletionReceiveRegistryChange,
        ["completion_writer_reentrancy_uses_snapshot"]=CompletionWriterSnapshot,
        ["building_unloaded_name_survives_resave"]=BuildingUnloadedResave,
        ["building_unloaded_name_is_omitted_from_wire"]=BuildingUnloadedWire,
        ["building_returning_content_reactivates"]=BuildingReturningContent,
        ["building_registry_reorder_preserves_identity"]=BuildingRegistryReorder,
        ["building_load_wrong_type_rolls_back"]=BuildingLoadWrongType,
        ["building_send_rejects_invalid_registry_without_writing"]=BuildingSendInvalidRegistry,
        ["building_receive_registry_change_rolls_back"]=BuildingReceiveRegistryChange,
        ["building_receive_rejects_global_location_budget"]=BuildingReceiveGlobalBudget,
        ["building_send_rejects_global_location_budget_without_writing"]=BuildingSendGlobalBudget,
        ["building_save_validation_is_nonmutating"]=BuildingSaveNonmutating,
        ["building_trim_reentrant_mutation_is_not_clobbered"]=BuildingTrimReentrant,
        ["world_load_is_transactional_across_tag_sections"]=WorldLoadTransactional,
        ["world_send_rejects_invalid_registry_without_writing"]=WorldSendInvalidRegistry,
        ["world_save_invalid_registry_leaves_tag_untouched"]=WorldSaveInvalidRegistry,
        ["duplicate_registry_names_fail_closed"]=DuplicateRegistryNames,
        ["world_receive_registry_change_rolls_back_both"]=WorldReceiveRegistryChange,
        ["world_writer_reentrancy_uses_one_snapshot"]=WorldWriterSnapshot,
        ["building_buff_reentrant_mutation_uses_snapshot"]=BuffReentrantSnapshot,
        ["selected_bounty_follows_stable_name_after_reorder"]=SelectedBountyReorder,
        ["selected_bounty_survives_unload_and_return"]=SelectedBountyUnloadReturn,
        ["selected_bounty_invalid_registry_fails_closed"]=SelectedBountyInvalidRegistry,
        ["player_load_invalid_registry_rolls_back"]=PlayerLoadInvalidRegistry,
        ["building_buff_registry_reorder_uses_stable_identity"]=BuffRegistryReorder,
    };
    public static int Main(string[] args){if(args.Length!=1||!Cases.TryGetValue(args[0],out var t))return 2;try{TestHooks.Reset();t();Console.WriteLine("PASS");return 0;}catch(Exception e){Console.Error.WriteLine(e);return 1;}}
    static void Check(bool c,string m){if(!c)throw new InvalidOperationException(m);}
    static BuildChallenge Challenge(string name,int steps=1,Action<IScanResults[],Rectangle> scan=null){var c=new BuildChallenge{Type=BuildChallengeLoader.BuildChallengeCount,FullName=name,Steps=new object[steps],PopulateAction=scan};BuildChallengeLoader.registeredBuildChallenges.Add(c);return c;}
    static BuildChallengeSaveData Data(params string[] names){var d=new BuildChallengeSaveData("K");d.Challenges.AddRange(names);return d;}
    static byte[] Write(Action<BinaryWriter> action){using var s=new MemoryStream();using var w=new BinaryWriter(s);action(w);w.Flush();return s.ToArray();}
    static BinaryReader Reader(byte[] b)=>new(new MemoryStream(b));
    static void ExpectInvalid(Action a){try{a();}catch(InvalidDataException){return;}throw new InvalidOperationException("expected InvalidDataException");}
    static void ExpectInvalidOperation(Action a){try{a();}catch(InvalidOperationException){return;}throw new InvalidOperationException("expected InvalidOperationException");}
    static Rectangle R(int x,int y,int w=2,int h=2)=>new(x,y,w,h);
    static void CompletionTrim(){var d=Data("b","a","b","c","a");d.TrimData();Check(d.Challenges.SequenceEqual(new[]{"b","a","c"}),"unstable dedup");}
    static void CompletionAdd(){var a=Challenge("A");var d=Data();d.Add(a);d.Add(a);Check(d.Challenges.SequenceEqual(new[]{"A"}),"duplicate add");}
    static void SaveCopies(){var d=Data("A");var t=new TagCompound();d.SaveData(t);d.Challenges.Add("B");Check(t.Get<List<string>>("K").SequenceEqual(new[]{"A"}),"tag aliases live list");}
    static void LoadCanonical(){var d=Data("stale");var t=new TagCompound{{"K",new List<string>{"A","A","B"}}};d.LoadData(t);Check(d.Challenges.SequenceEqual(new[]{"A","B"}),"load not canonical");}
    static void UnknownPersists(){var d=Data("Gone/Thing");var t=new TagCompound();d.SaveData(t);var e=Data();e.LoadData(t);Check(e.Challenges.Single()=="Gone/Thing","unknown lost");}
    static void CompletionGlobalIds(){Challenge("A");var b=Challenge("B");var c=Challenge("C");var d=Data(b.FullName,c.FullName);byte[] f=Write(d.SendData);using var r=Reader(f);Check(r.ReadInt32()==2&&r.ReadInt32()==1&&r.ReadInt32()==2,"subset positions used");}
    static void CompletionSorted(){var a=Challenge("A");var b=Challenge("B");var c=Challenge("C");var d=Data(c.FullName,a.FullName,c.FullName,b.FullName);using var r=Reader(Write(d.SendData));Check(r.ReadInt32()==3&&r.ReadInt32()==0&&r.ReadInt32()==1&&r.ReadInt32()==2,"wire ids not sorted unique");}
    static void UnknownOmittedWire(){Challenge("A");var d=Data("Gone","A");using var r=Reader(Write(d.SendData));Check(r.ReadInt32()==1&&r.ReadInt32()==0&&d.Challenges.Contains("Gone"),"unknown handling");}
    static void CompletionReceive(){Challenge("A");Challenge("B");var d=Data("stale");using var r=Reader(Write(w=>{w.Write(1);w.Write(1);}));d.RecieveData(r);Check(d.Challenges.SequenceEqual(new[]{"B"}),"receive replace");}
    static void BadCompletion(byte[] frame){Challenge("A");Challenge("B");var d=Data("keep");using var r=Reader(frame);ExpectInvalid(()=>d.RecieveData(r));Check(d.Challenges.SequenceEqual(new[]{"keep"}),"completion rollback");}
    static void CompletionNegative()=>BadCompletion(Write(w=>w.Write(-1)));
    static void CompletionLarge()=>BadCompletion(Write(w=>w.Write(3)));
    static void CompletionDuplicate()=>BadCompletion(Write(w=>{w.Write(2);w.Write(0);w.Write(0);}));
    static void CompletionRange()=>BadCompletion(Write(w=>{w.Write(1);w.Write(2);}));
    static void CompletionTruncated()=>BadCompletion(Write(w=>{w.Write(2);w.Write(0);}));
    static void CompletionUnsorted()=>BadCompletion(Write(w=>{w.Write(2);w.Write(1);w.Write(0);}));
    static string Key(BuildChallenge c)=>$"BuildingBuffs_{c.FullName}";
    static void BuildingLoadContinue(){var a=Challenge("A");var b=Challenge("B");var t=new TagCompound{{Key(b),new List<Rectangle>{R(4,4)}}};CarpentrySystem.BuildingBuffs.LoadData(t);Check(!CarpentrySystem.BuildingBuffs.AnyBuild(a.Type)&&CarpentrySystem.BuildingBuffs.AnyBuild(b.Type),"stopped at missing key");}
    static void BuildingLoadClears(){var a=Challenge("A");CarpentrySystem.BuildingBuffs.WorldData[a.Type]=new(){R(0,0)};CarpentrySystem.BuildingBuffs.LoadData(new TagCompound());Check(CarpentrySystem.BuildingBuffs.WorldData.Count==0,"stale building remained");}
    static void BuildingLoadCopies(){var a=Challenge("A");var list=new List<Rectangle>{R(1,1)};var t=new TagCompound{{Key(a),list}};CarpentrySystem.BuildingBuffs.LoadData(t);list.Clear();Check(CarpentrySystem.BuildingBuffs.WorldData[a.Type].Count==1,"tag list aliased");}
    static void WorldSavePreserves(){var a=Challenge("A",0);CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(0,0));new CarpentrySystem().SaveWorldData(new TagCompound());Check(CarpentrySystem.BuildingBuffs.AnyBuild(a.Type),"save cleared live state");}
    static void WorldSaveLoadBoth(){var a=Challenge("A",0);CarpentrySystem.CompletedBounties.Add(a);CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(0,0));var system=new CarpentrySystem();var tag=new TagCompound();system.SaveWorldData(tag);system.ClearWorld();system.LoadWorldData(tag);Check(CarpentrySystem.CompletedBounties.ContainsChallenge(a)&&CarpentrySystem.BuildingBuffs.AnyBuild(a.Type),"world save/load lost a store");}
    static void ClearWorldBoth(){var a=Challenge("A");CarpentrySystem.CompletedBounties.Add(a);CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(0,0));new CarpentrySystem().ClearWorld();Check(CarpentrySystem.CompletedBounties.Challenges.Count==0&&CarpentrySystem.BuildingBuffs.WorldData.Count==0,"clear world incomplete");}
    static void BuildingSaveFilters(){var a=Challenge("A",0);CarpentrySystem.BuildingBuffs.WorldData[a.Type]=new(){R(0,0),R(int.MaxValue,0,2,2),R(1,1)};CarpentrySystem.BuildingBuffs.WorldData[99]=new(){R(9,9)};var tag=new TagCompound();CarpentrySystem.BuildingBuffs.SaveData(tag);var saved=tag.Get<List<Rectangle>>(Key(a));Check(tag.Count==1&&saved.Count==1&&saved[0].X==0&&CarpentrySystem.BuildingBuffs.WorldData.ContainsKey(99),"save did not snapshot only canonical registered state");}
    static void BuildingLoadFiltersOverflow(){var a=Challenge("A");var tag=new TagCompound{{Key(a),new List<Rectangle>{R(int.MaxValue,0,2,2),R(5,5)}}};CarpentrySystem.BuildingBuffs.LoadData(tag);Check(CarpentrySystem.BuildingBuffs.WorldData[a.Type].Single().X==5,"overflowing saved rectangle survived load");}
    static void TrimEveryStep(){int calls=0;var a=Challenge("A",3,(res,rect)=>{for(int i=0;i<res.Length;i++){calls++;res[i]=new ScanResult{ResultType=StepResultType.Success};}});CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(0,0));CarpentrySystem.BuildingBuffs.TrimBuildingBuffsInWorld(a.Type);Check(calls==3&&CarpentrySystem.BuildingBuffs.AnyBuild(a.Type),"scan stalled/skipped");}
    static void TrimFailContinues(){var a=Challenge("A",1,(res,rect)=>res[0]=new ScanResult{ResultType=rect.X==0?StepResultType.Fail:StepResultType.Success});CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(0,0));CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(5,0));CarpentrySystem.BuildingBuffs.TrimBuildingBuffsInWorld(a.Type);Check(CarpentrySystem.BuildingBuffs.WorldData[a.Type].Single().X==5,"failed/later handling");}
    static void TrimExceptionContinues(){var a=Challenge("A",1,(res,rect)=>{if(rect.X==0)throw new Exception("boom");res[0]=new ScanResult{ResultType=StepResultType.Success};});CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(0,0));CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(5,0));CarpentrySystem.BuildingBuffs.TrimBuildingBuffsInWorld(a.Type);Check(CarpentrySystem.BuildingBuffs.WorldData[a.Type].Single().X==5&&Aequus.Aequus.Instance.Logger.Errors.Count==1,"exception isolation");}
    static void AddUnknown(){Challenge("A");Check(!CarpentrySystem.BuildingBuffs.AddBuild(3,R(0,0)),"unknown accepted");}
    static void AddBadRectangle(){var a=Challenge("A");Check(!CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(0,0,0,2)),"bad rect accepted");}
    static void AddOverlap(){var a=Challenge("A");Check(CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(0,0))&&!CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(1,1)),"overlap accepted");}
    static void AddOverflow(){var a=Challenge("A");Check(!CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(int.MaxValue,0,2,2))&&!CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(0,int.MaxValue,2,2)),"overflowing rectangle accepted");}
    static BinaryReader BuildingFrame(){return Reader(Write(CarpentrySystem.BuildingBuffs.NetSend));}
    static void BuildingSendSorted(){var a=Challenge("A");var b=Challenge("B");CarpentrySystem.BuildingBuffs.WorldData[b.Type]=new(){R(5,0)};CarpentrySystem.BuildingBuffs.WorldData[a.Type]=new(){R(0,0)};using var r=BuildingFrame();Check(r.ReadInt32()==2&&r.ReadInt32()==0,"groups not sorted");}
    static void BuildingSendCount(){var a=Challenge("A");var b=Challenge("B");CarpentrySystem.BuildingBuffs.WorldData[a.Type]=new();CarpentrySystem.BuildingBuffs.WorldData[b.Type]=new(){R(0,0)};using var r=BuildingFrame();Check(r.ReadInt32()==1&&r.ReadInt32()==b.Type,"count mismatch");}
    static void BuildingSkipEmpty(){var a=Challenge("A");var b=Challenge("B");CarpentrySystem.BuildingBuffs.WorldData[a.Type]=new();CarpentrySystem.BuildingBuffs.WorldData[b.Type]=new();using var r=BuildingFrame();Check(r.ReadInt32()==0&&r.BaseStream.Position==r.BaseStream.Length,"empty groups emitted");}
    static byte[] BFrame(Action<BinaryWriter> body)=>Write(body);
    static void BuildingReceive(){Challenge("A");Challenge("B");CarpentrySystem.BuildingBuffs.WorldData[0]=new(){R(9,9)};using var r=Reader(BFrame(w=>{w.Write(1);w.Write(1);w.Write(1);w.Write(2);w.Write(3);w.Write(4);w.Write(5);}));CarpentrySystem.BuildingBuffs.NetReceive(r);Check(CarpentrySystem.BuildingBuffs.WorldData.Count==1&&CarpentrySystem.BuildingBuffs.WorldData[1].Single().X==2,"building replace");}
    static void BadBuilding(byte[] frame){Challenge("A");Challenge("B");CarpentrySystem.BuildingBuffs.WorldData[0]=new(){R(9,9)};using var r=Reader(frame);ExpectInvalid(()=>CarpentrySystem.BuildingBuffs.NetReceive(r));Check(CarpentrySystem.BuildingBuffs.WorldData[0].Single().X==9,"building rollback");}
    static void BuildingNegative()=>BadBuilding(BFrame(w=>w.Write(-1)));
    static void BuildingDuplicate()=>BadBuilding(BFrame(w=>{w.Write(2);for(int i=0;i<2;i++){w.Write(0);w.Write(1);w.Write(i*5);w.Write(0);w.Write(2);w.Write(2);}}));
    static void BuildingUnknown()=>BadBuilding(BFrame(w=>{w.Write(1);w.Write(2);w.Write(1);}));
    static void BuildingLarge()=>BadBuilding(BFrame(w=>{w.Write(1);w.Write(0);w.Write(4097);}));
    static void BuildingEmpty()=>BadBuilding(BFrame(w=>{w.Write(1);w.Write(0);w.Write(0);}));
    static void BuildingBadRect()=>BadBuilding(BFrame(w=>{w.Write(1);w.Write(0);w.Write(1);w.Write(0);w.Write(0);w.Write(0);w.Write(2);}));
    static void BuildingOverlap()=>BadBuilding(BFrame(w=>{w.Write(1);w.Write(0);w.Write(2);foreach(var x in new[]{0,1}){w.Write(x);w.Write(0);w.Write(2);w.Write(2);}}));
    static void BuildingTruncated()=>BadBuilding(BFrame(w=>{w.Write(1);w.Write(0);w.Write(1);w.Write(0);}));
    static void BuildingUnsorted()=>BadBuilding(BFrame(w=>{w.Write(2);foreach(var id in new[]{1,0}){w.Write(id);w.Write(1);w.Write(id*5);w.Write(0);w.Write(2);w.Write(2);}}));
    static void BuildingOverflow()=>BadBuilding(BFrame(w=>{w.Write(1);w.Write(0);w.Write(1);w.Write(int.MaxValue);w.Write(0);w.Write(2);w.Write(2);}));
    static void WorldSyncOrder(){var a=Challenge("A");CarpentrySystem.CompletedBounties.Add(a);CarpentrySystem.BuildingBuffs.AddBuild(0,R(1,2));using var r=Reader(Write(new CarpentrySystem().NetSend));Check(r.ReadInt32()==1&&r.ReadInt32()==0&&r.ReadInt32()==1&&r.ReadInt32()==0,"world section order");}
    static void WorldSyncRollback(){var a=Challenge("A");var b=Challenge("B");CarpentrySystem.CompletedBounties.Add(a);CarpentrySystem.BuildingBuffs.AddBuild(0,R(9,9));byte[] f=Write(w=>{w.Write(1);w.Write(1);w.Write(1);w.Write(0);w.Write(1);w.Write(0);});using var r=Reader(f);ExpectInvalid(()=>new CarpentrySystem().NetReceive(r));Check(CarpentrySystem.CompletedBounties.ContainsChallenge(a)&&CarpentrySystem.BuildingBuffs.WorldData[0].Single().X==9,"world rollback");}
    static void ClientComplete(){var a=Challenge("A");Terraria.Main.netMode=NetmodeID.MultiplayerClient;CarpentrySystem.Complete(a);Check(!CarpentrySystem.CompletedBounties.ContainsChallenge(a)&&Aequus.Aequus.Packets.Single().Type==PacketType.CompleteCarpenterBounty,"client complete");}
    static void ServerComplete(){var a=Challenge("A");Terraria.Main.netMode=NetmodeID.Server;CarpentrySystem.Complete(a);CarpentrySystem.Complete(a);Check(CarpentrySystem.CompletedBounties.Challenges.Count==1&&Aequus.Aequus.Packets.Count==1&&Aequus.Aequus.Packets[0].Sent,"server duplicate broadcast");}
    static void ServerReset(){var a=Challenge("A");CarpentrySystem.CompletedBounties.Add(a);Terraria.Main.netMode=NetmodeID.Server;CarpentrySystem.ResetBounties();Check(CarpentrySystem.CompletedBounties.Challenges.Count==0&&Aequus.Aequus.Packets.Single().Sent,"server reset");}
    static void AddPacketOnChange(){var a=Challenge("A");Terraria.Main.netMode=NetmodeID.Server;Check(CarpentrySystem.AddBuildingBuffLocation(a.Type,R(0,0))&&!CarpentrySystem.AddBuildingBuffLocation(a.Type,R(1,1))&&Aequus.Aequus.Packets.Count==1,"add packet count");}
    static void QuietNoEcho(){var a=Challenge("A");Terraria.Main.netMode=NetmodeID.Server;CarpentrySystem.AddBuildingBuffLocation(a.Type,R(0,0),true);Check(Aequus.Aequus.Packets.Count==0,"quiet echoed");}
    static void RemovePacketOnChange(){var a=Challenge("A");CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(0,0));Terraria.Main.netMode=NetmodeID.Server;Check(CarpentrySystem.RemoveBuildingBuffLocation(a.Type,1,1)&&!CarpentrySystem.RemoveBuildingBuffLocation(a.Type,1,1)&&Aequus.Aequus.Packets.Count==1,"remove packet count");}
    static CarpentryPlayer PlayerState(string name){var p=new CarpentryPlayer();p.CollectedBounties.Challenges.Add(name);p.SelectedBounty=0;return p;}
    static void PlayerClone(){Challenge("A");var p=PlayerState("A");var c=(CarpentryPlayer)p.Clone(new Player());c.CollectedBounties.Challenges.Add("B");Check(p.CollectedBounties.Challenges.SequenceEqual(new[]{"A"})&&c.SelectedBounty==0,"clone alias/state");}
    static void ClientCopy(){Challenge("A");var p=PlayerState("A");var c=new CarpentryPlayer();p.CopyClientState(c);Check(c.CollectedBounties.Challenges.SequenceEqual(new[]{"A"})&&c.SelectedBounty==0,"client state not copied");c.CollectedBounties.Challenges.Clear();Check(p.CollectedBounties.Challenges.SequenceEqual(new[]{"A"}),"client clone alias");}
    static void InvalidSelectedBounty(){Challenge("A");var p=new CarpentryPlayer{SelectedBounty=4};var tag=new TagCompound();p.SaveData(tag);Check(!tag.ContainsKey("SelectedBounty"),"invalid selected bounty saved");}
    static CarpentryPlayer BuffPlayer(){var state=new CarpentryPlayer{Player=new Player{whoAmI=0,Center=new Vector2(160,160)}};state.Player.AequusData.buildingBuffRange=10;return state;}
    static void BuffChallengeZero(){var a=Challenge("A");a.BuildBuffType=7;CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(9,9));var p=BuffPlayer();p.CheckBuffBuildings();Check(p.Player.Buffs.SequenceEqual(new[]{(7,60)}),"challenge zero did not grant its buff");}
    static void BuffOncePerGroup(){Challenge("Unused");var a=Challenge("A");a.BuildBuffType=8;CarpentrySystem.BuildingBuffs.WorldData[a.Type]=new(){R(8,8),R(9,9)};var p=BuffPlayer();p.CheckBuffBuildings();Check(p.Player.Buffs.SequenceEqual(new[]{(8,60)}),"one group granted its buff more than once");}
    static void BuffIgnoresInapplicable(){var a=Challenge("A");a.BuildBuffType=0;var b=Challenge("B");b.BuildBuffType=9;CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(9,9));CarpentrySystem.BuildingBuffs.AddBuild(b.Type,R(100,100));var p=BuffPlayer();p.CheckBuffBuildings();Check(p.Player.Buffs.Count==0,"inapplicable building granted a buff");}
    static void BuffIgnoresStale(){var a=Challenge("A");a.BuildBuffType=9;CarpentrySystem.BuildingBuffs.WorldData[a.Type]=null;CarpentrySystem.BuildingBuffs.WorldData[99]=new(){R(9,9)};var p=BuffPlayer();p.CheckBuffBuildings();Check(p.Player.Buffs.Count==0,"stale building state was not ignored");}
    static void PostUpdateGate(){Challenge("Unused");var a=Challenge("A");a.BuildBuffType=9;CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(9,9));var p=BuffPlayer();Terraria.Main.myPlayer=1;Terraria.Main.GameUpdateCount=10;p.PostUpdate();Terraria.Main.myPlayer=0;Terraria.Main.GameUpdateCount=9;p.PostUpdate();Terraria.Main.GameUpdateCount=10;Terraria.NPC.Danger=true;p.PostUpdate();Terraria.NPC.Danger=false;p.PostUpdate();Check(p.Player.Buffs.SequenceEqual(new[]{(9,60)}),"post-update ownership/tick/danger gate mismatch");}
    static void CompletionLoadWrongType(){var d=Data("keep");var tag=new TagCompound{{"K","bad"}};ExpectInvalid(()=>d.LoadData(tag));Check(d.Challenges.SequenceEqual(new[]{"keep"}),"corrupt completion tag mutated state");}
    static void CompletionSendInvalidRegistry(){var a=Challenge("A");var d=Data("A");a.Type=1;using var stream=new MemoryStream();using var writer=new BinaryWriter(stream);ExpectInvalidOperation(()=>d.SendData(writer));Check(stream.Length==0,"invalid registry emitted completion bytes");}
    static void CompletionReceiveRegistryChange(){Challenge("A");var d=Data("keep");byte[] frame=Write(w=>{w.Write(1);w.Write(0);});using var stream=new CallbackReadStream(frame,4,()=>BuildChallengeLoader.registeredBuildChallenges[0]=new BuildChallenge{Type=0,FullName="A",Steps=new object[1]});using var reader=new BinaryReader(stream);ExpectInvalid(()=>d.RecieveData(reader));Check(d.Challenges.SequenceEqual(new[]{"keep"}),"registry-changing completion receive committed");}
    static void CompletionWriterSnapshot(){Challenge("A");var d=Data("A");using var stream=new CallbackWriteStream(()=>BuildChallengeLoader.registeredBuildChallenges.Clear());using(var writer=new BinaryWriter(stream,System.Text.Encoding.UTF8,true))d.SendData(writer);using var reader=Reader(stream.ToArray());Check(reader.ReadInt32()==1&&reader.ReadInt32()==0,"completion writer callback changed prepared frame");}
    static void BuildingUnloadedResave(){var input=new TagCompound{{"BuildingBuffs_Gone",new List<Rectangle>{R(3,4)}}};CarpentrySystem.BuildingBuffs.LoadData(input);var output=new TagCompound();CarpentrySystem.BuildingBuffs.SaveData(output);Check(output.TryGet("BuildingBuffs_Gone",out List<Rectangle> saved)&&saved.Single().X==3,"unloaded building identity was lost");}
    static void BuildingUnloadedWire(){var input=new TagCompound{{"BuildingBuffs_Gone",new List<Rectangle>{R(3,4)}}};CarpentrySystem.BuildingBuffs.LoadData(input);using var reader=BuildingFrame();Check(reader.ReadInt32()==0&&reader.BaseStream.Position==reader.BaseStream.Length,"unloaded group leaked to wire");var output=new TagCompound();CarpentrySystem.BuildingBuffs.SaveData(output);Check(output.ContainsKey("BuildingBuffs_Gone"),"wire omission deleted unloaded group");}
    static void BuildingReturningContent(){CarpentrySystem.BuildingBuffs.LoadData(new TagCompound{{"BuildingBuffs_Gone",new List<Rectangle>{R(3,4)}}});var challenge=Challenge("Gone");Check(CarpentrySystem.BuildingBuffs.AnyBuild(challenge.Type)&&CarpentrySystem.BuildingBuffs.WorldData[challenge.Type].Single().X==3,"returning content did not reactivate");}
    static void BuildingRegistryReorder(){var a=Challenge("A");var b=Challenge("B");CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(1,0));CarpentrySystem.BuildingBuffs.AddBuild(b.Type,R(9,0));BuildChallengeLoader.registeredBuildChallenges[0]=b;BuildChallengeLoader.registeredBuildChallenges[1]=a;b.Type=0;a.Type=1;Check(CarpentrySystem.BuildingBuffs.AnyBuild(1)&&CarpentrySystem.BuildingBuffs.WorldData[1].Single().X==1&&CarpentrySystem.BuildingBuffs.AnyBuild(0)&&CarpentrySystem.BuildingBuffs.WorldData[0].Single().X==9,"registry reorder rebound geometry by old id");}
    static void BuildingLoadWrongType(){var a=Challenge("A");CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(9,9));var tag=new TagCompound{{Key(a),"bad"}};ExpectInvalid(()=>CarpentrySystem.BuildingBuffs.LoadData(tag));Check(CarpentrySystem.BuildingBuffs.WorldData[a.Type].Single().X==9,"corrupt building tag mutated state");}
    static void BuildingSendInvalidRegistry(){var a=Challenge("A");CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(0,0));a.Type=1;using var stream=new MemoryStream();using var writer=new BinaryWriter(stream);ExpectInvalidOperation(()=>CarpentrySystem.BuildingBuffs.NetSend(writer));Check(stream.Length==0,"invalid registry emitted building bytes");}
    static void BuildingReceiveRegistryChange(){Challenge("A");CarpentrySystem.BuildingBuffs.AddBuild(0,R(9,9));byte[] frame=BFrame(w=>{w.Write(1);w.Write(0);w.Write(1);w.Write(0);w.Write(0);w.Write(2);w.Write(2);});using var stream=new CallbackReadStream(frame,12,()=>BuildChallengeLoader.registeredBuildChallenges[0]=new BuildChallenge{Type=0,FullName="A",Steps=new object[1]});using var reader=new BinaryReader(stream);ExpectInvalid(()=>CarpentrySystem.BuildingBuffs.NetReceive(reader));Check(CarpentrySystem.BuildingBuffs.WorldData[0].Single().X==9,"registry-changing building receive committed");}
    static void BuildingReceiveGlobalBudget(){byte[] frame=BFrame(w=>{w.Write(2);w.Write(0);w.Write(4096);for(int i=0;i<4096;i++){w.Write(i*2);w.Write(0);w.Write(1);w.Write(1);}w.Write(1);w.Write(1);w.Write(0);w.Write(4);w.Write(1);w.Write(1);});BadBuilding(frame);}
    static void BuildingSendGlobalBudget(){Challenge("A");Challenge("B");var first=new List<Rectangle>();var second=new List<Rectangle>();for(int i=0;i<2049;i++){first.Add(R(i*2,0,1,1));second.Add(R(i*2,4,1,1));}CarpentrySystem.BuildingBuffs.WorldData[0]=first;CarpentrySystem.BuildingBuffs.WorldData[1]=second;using var stream=new MemoryStream();using var writer=new BinaryWriter(stream);ExpectInvalidOperation(()=>CarpentrySystem.BuildingBuffs.NetSend(writer));Check(stream.Length==0,"oversized building snapshot emitted bytes");}
    static void BuildingSaveNonmutating(){var a=Challenge("A",1,(results,rectangle)=>results[0]=new ScanResult{ResultType=rectangle.X==0?StepResultType.Fail:StepResultType.Success});CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(0,0));CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(5,0));var tag=new TagCompound();CarpentrySystem.BuildingBuffs.SaveData(tag);Check(CarpentrySystem.BuildingBuffs.WorldData[a.Type].Count==2&&tag.Get<List<Rectangle>>(Key(a)).Single().X==5,"save validation mutated live buildings");}
    static void BuildingTrimReentrant(){BuildChallenge a=null;a=Challenge("A",1,(results,rectangle)=>{CarpentrySystem.BuildingBuffs.WorldData[a.Type].Add(R(10,0));results[0]=new ScanResult{ResultType=StepResultType.Fail};});CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(0,0));CarpentrySystem.BuildingBuffs.TrimBuildingBuffsInWorld(a.Type);Check(CarpentrySystem.BuildingBuffs.WorldData[a.Type].Count==2&&CarpentrySystem.BuildingBuffs.WorldData[a.Type].Any(r=>r.X==10),"trim clobbered reentrant mutation");}
    static void WorldLoadTransactional(){var a=Challenge("A");var b=Challenge("B");CarpentrySystem.CompletedBounties.Add(a);CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(9,9));var tag=new TagCompound{{"CompletedBounties",new List<string>{"B"}},{Key(a),"bad"}};ExpectInvalid(()=>new CarpentrySystem().LoadWorldData(tag));Check(CarpentrySystem.CompletedBounties.ContainsChallenge(a)&&CarpentrySystem.BuildingBuffs.WorldData[a.Type].Single().X==9,"world tag load committed one section");}
    static void WorldSendInvalidRegistry(){var a=Challenge("A");CarpentrySystem.CompletedBounties.Add(a);a.Type=1;using var stream=new MemoryStream();using var writer=new BinaryWriter(stream);ExpectInvalidOperation(()=>new CarpentrySystem().NetSend(writer));Check(stream.Length==0,"invalid registry emitted world bytes");}
    static void WorldSaveInvalidRegistry(){var a=Challenge("A");CarpentrySystem.CompletedBounties.Add(a);var tag=new TagCompound{{"Keep",7}};a.Type=1;ExpectInvalidOperation(()=>new CarpentrySystem().SaveWorldData(tag));Check(tag.Count==1&&tag.Get<int>("Keep")==7,"invalid-registry world save partially changed destination tag");}
    static void DuplicateRegistryNames(){Challenge("A");var duplicate=Challenge("B");duplicate.FullName="A";using var stream=new MemoryStream();using var writer=new BinaryWriter(stream);ExpectInvalidOperation(()=>new CarpentrySystem().NetSend(writer));Check(stream.Length==0,"duplicate registry names did not fail before output");}
    static void WorldReceiveRegistryChange(){var a=Challenge("A");Challenge("B");CarpentrySystem.CompletedBounties.Add(a);CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(9,9));byte[] frame=Write(w=>{w.Write(1);w.Write(1);w.Write(0);});using var stream=new CallbackReadStream(frame,4,()=>BuildChallengeLoader.registeredBuildChallenges[0]=new BuildChallenge{Type=0,FullName="A",Steps=new object[1]});using var reader=new BinaryReader(stream);ExpectInvalid(()=>new CarpentrySystem().NetReceive(reader));Check(CarpentrySystem.CompletedBounties.Challenges.SequenceEqual(new[]{"A"})&&CarpentrySystem.BuildingBuffs.WorldData[0].Single().X==9,"registry-changing world receive committed");}
    static void WorldWriterSnapshot(){var a=Challenge("A");CarpentrySystem.CompletedBounties.Add(a);CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(1,2));using var stream=new CallbackWriteStream(()=>{CarpentrySystem.CompletedBounties.Clear();CarpentrySystem.BuildingBuffs.Clear();BuildChallengeLoader.registeredBuildChallenges.Clear();});using(var writer=new BinaryWriter(stream,System.Text.Encoding.UTF8,true))new CarpentrySystem().NetSend(writer);using var reader=Reader(stream.ToArray());Check(reader.ReadInt32()==1&&reader.ReadInt32()==0&&reader.ReadInt32()==1&&reader.ReadInt32()==0&&reader.ReadInt32()==1,"world writer callback mixed generations");}
    static void BuffReentrantSnapshot(){var a=Challenge("A");var b=Challenge("B");a.BuildBuffType=7;b.BuildBuffType=8;CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(9,9));CarpentrySystem.BuildingBuffs.AddBuild(b.Type,R(8,8));var player=BuffPlayer();player.Player.OnAddBuff=(_,__)=>CarpentrySystem.BuildingBuffs.Clear();player.CheckBuffBuildings();Check(player.Player.Buffs.SequenceEqual(new[]{(7,60),(8,60)}),"buff callback invalidated live enumeration");}
    static void SelectedBountyReorder(){var a=Challenge("A");var b=Challenge("B");var player=new CarpentryPlayer{SelectedBounty=0};BuildChallengeLoader.registeredBuildChallenges[0]=b;BuildChallengeLoader.registeredBuildChallenges[1]=a;b.Type=0;a.Type=1;var tag=new TagCompound();player.SaveData(tag);Check(tag.Get<string>("SelectedBounty")=="A"&&player.SelectedBounty==1,"selected bounty followed transient id");}
    static void SelectedBountyUnloadReturn(){Challenge("A");var player=new CarpentryPlayer();player.LoadData(new TagCompound{{"SelectedBounty","A"}});BuildChallengeLoader.registeredBuildChallenges.Clear();var dormantTag=new TagCompound();player.SaveData(dormantTag);Check(player.SelectedBounty==-1&&dormantTag.Get<string>("SelectedBounty")=="A","unloaded selected bounty identity was discarded");var returned=Challenge("A");Check(player.SelectedBounty==returned.Type,"returning selected bounty did not reactivate");}
    static void SelectedBountyInvalidRegistry(){var a=Challenge("A");var player=new CarpentryPlayer{SelectedBounty=0};a.Type=1;Check(player.SelectedBounty==-1,"invalid registry exposed a stale selected id");var tag=new TagCompound();player.SaveData(tag);Check(tag.Get<string>("SelectedBounty")=="A","fail-closed query discarded stable selected identity");a.Type=0;Check(player.SelectedBounty==0,"selected identity did not rebind after registry recovery");}
    static void PlayerLoadInvalidRegistry(){var a=Challenge("A");var player=new CarpentryPlayer{SelectedBounty=0,CanClaimFreeShutterstockerGift=true};player.CollectedBounties.Add(a);var incoming=new TagCompound{{"FreeCamera",false},{"SelectedBounty","B"},{"CollectedBounties",new List<string>{"B"}}};a.Type=1;ExpectInvalid(()=>player.LoadData(incoming));a.Type=0;var saved=new TagCompound();player.SaveData(saved);Check(player.CanClaimFreeShutterstockerGift&&player.SelectedBounty==0&&player.CollectedBounties.Challenges.SequenceEqual(new[]{"A"})&&saved.Get<string>("SelectedBounty")=="A","invalid-registry player load partially committed");}
    static void BuffRegistryReorder(){var a=Challenge("A");var b=Challenge("B");a.BuildBuffType=7;b.BuildBuffType=8;CarpentrySystem.BuildingBuffs.AddBuild(a.Type,R(9,9));BuildChallengeLoader.registeredBuildChallenges[0]=b;BuildChallengeLoader.registeredBuildChallenges[1]=a;b.Type=0;a.Type=1;var player=BuffPlayer();player.CheckBuffBuildings();Check(player.Player.Buffs.SequenceEqual(new[]{(7,60)}),"buff geometry rebound to reordered registry id");}

    sealed class CallbackReadStream:MemoryStream
    {
        readonly long threshold;readonly Action callback;bool fired;
        public CallbackReadStream(byte[] bytes,long threshold,Action callback):base(bytes){this.threshold=threshold;this.callback=callback;}
        void Fire(){if(!fired&&Position>=threshold){fired=true;callback();}}
        public override int Read(byte[] buffer,int offset,int count){int read=base.Read(buffer,offset,count);Fire();return read;}
        public override int Read(Span<byte> buffer){int read=base.Read(buffer);Fire();return read;}
        public override int ReadByte(){int value=base.ReadByte();Fire();return value;}
    }

    sealed class CallbackWriteStream:MemoryStream
    {
        readonly Action callback;bool fired;
        public CallbackWriteStream(Action callback){this.callback=callback;}
        void Fire(){if(!fired){fired=true;callback();}}
        public override void Write(byte[] buffer,int offset,int count){Fire();base.Write(buffer,offset,count);}
        public override void Write(ReadOnlySpan<byte> buffer){Fire();base.Write(buffer);}
        public override void WriteByte(byte value){Fire();base.WriteByte(value);}
    }
}
