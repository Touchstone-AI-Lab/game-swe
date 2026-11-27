using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SpiritMod;
using SpiritMod.Mechanics.QuestSystem;
using SpiritMod.Mechanics.QuestSystem.Tasks;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

internal static class ContractProgram
{
    private static readonly Dictionary<string, Action> Cases = new()
    {
        ["completion_requires_three_consecutive_checks"] = CompletionRequiresThree,
        ["false_check_resets_completion_debounce"] = FalseResetsDebounce,
        ["task_transition_resets_completion_debounce"] = TransitionResetsDebounce,
        ["branch_identity_change_restarts_debounce"] = BranchIdentityRestartsDebounce,
        ["branch_chooses_first_completed_candidate"] = BranchChoosesFirst,
        ["branch_remembers_stable_slot_and_successor"] = BranchRemembersSlot,
        ["branch_reset_clears_choice_and_children"] = BranchResetClears,
        ["branch_rejects_unrepresentable_slot"] = BranchRejectsUnrepresentableSlot,
        ["branch_constructor_snapshots_input"] = BranchConstructorSnapshotsInput,
        ["branch_rejects_null_child"] = BranchRejectsNullChild,
        ["branch_deactivate_without_choice_covers_all"] = BranchDeactivateWithoutChoice,
        ["branch_deactivate_during_pending_choice_covers_all"] = BranchDeactivateDuringPendingChoice,
        ["local_completion_sends_before_mutation"] = LocalSendsBeforeMutation,
		["local_nonbranch_frame_uses_empty_path"] = LocalNonBranchEmptyPath,
        ["local_branch_completes_selected_child_only"] = LocalBranchSelectedOnly,
        ["local_branch_frame_uses_wrapper_identity"] = LocalBranchWrapperIdentity,
        ["quiet_completion_never_echoes"] = QuietNeverEchoes,
        ["remote_branch_completes_selected_child"] = RemoteBranchSelectedChild,
        ["remote_branch_activates_selected_successor"] = RemoteBranchSuccessor,
        ["remote_invalid_branch_slot_is_noop"] = RemoteInvalidBranchNoop,
        ["remote_stale_branch_frame_is_noop"] = RemoteStaleBranchNoop,
        ["task_buffer_preserves_variable_payload"] = TaskBufferVariablePayload,
        ["task_buffer_preserves_zero_payload"] = TaskBufferZeroPayload,
        ["task_buffer_switches_only_after_successful_read"] = TaskBufferSwitchAfterRead,
        ["task_buffer_rejects_short_header_without_replacement"] = TaskBufferShortHeader,
        ["task_buffer_rejects_unknown_id_without_replacement"] = TaskBufferUnknownId,
        ["task_buffer_rejects_truncated_payload_without_replacement"] = TaskBufferTruncated,
        ["task_buffer_rejects_trailing_payload"] = TaskBufferTrailing,
        ["task_buffer_restores_target_on_read_failure"] = TaskBufferRollback,
        ["task_buffer_same_task_does_not_reactivate"] = TaskBufferSameTaskNoLifecycle,
        ["task_buffer_rejects_oversize_before_write"] = TaskBufferOversize,
        ["branch_data_roundtrips_children_and_choice"] = BranchDataRoundtrip,
        ["branch_data_rejects_wrong_version_without_mutation"] = BranchDataWrongVersion,
        ["branch_data_rejects_topology_without_mutation"] = BranchDataWrongTopology,
        ["branch_data_rejects_truncation_without_mutation"] = BranchDataTruncated,
        ["branch_data_rolls_back_partial_child_read"] = BranchDataRollback,
        ["snapshot_flags_roundtrip_all_booleans"] = SnapshotBooleanRoundtrip,
        ["snapshot_flags_roundtrip_signed_countdowns"] = SnapshotSignedRoundtrip,
        ["snapshot_zero_buffer_has_zero_length"] = SnapshotZeroBuffer,
        ["snapshot_255_byte_buffer_is_exact"] = SnapshotMaxBuffer,
        ["snapshot_oversize_buffer_is_rejected_before_write"] = SnapshotOversizeRejected,
        ["server_rejects_unknown_quest_without_relay"] = ServerRejectsUnknownQuest,
        ["server_rejects_invalid_claimed_player"] = ServerRejectsInvalidPlayer,
        ["server_rejects_invalid_branch_slot_without_relay"] = ServerRejectsInvalidBranch,
        ["server_rejects_nonbranch_slot_without_relay"] = ServerRejectsNonBranchSlot,
        ["server_applies_once_before_relay"] = ServerAppliesBeforeRelay,
        ["server_relay_is_canonical_and_excludes_sender"] = ServerRelayCanonical,
        ["client_applies_canonical_progress_without_echo"] = ClientAppliesWithoutEcho,
        ["server_rejects_stale_task_identity"] = ServerRejectsStaleTask,
        ["client_rejects_stale_task_identity"] = ClientRejectsStaleTask,
        ["server_progress_rejects_trailing_frame"] = ServerProgressTrailing,
        ["client_progress_rejects_trailing_frame"] = ClientProgressTrailing,
        ["completion_restores_prior_quiet_state"] = CompletionRestoresQuiet,
        ["completion_restores_quiet_when_task_throws"] = CompletionRestoresOnThrow,
        ["activate_helper_restores_quiet_on_throw"] = ActivateRestoresOnThrow,
        ["deactivate_and_unlock_helpers_restore_quiet"] = OtherHelpersRestoreQuiet,
        ["server_activate_applies_before_canonical_relay"] = ServerActivateTransition,
        ["server_deactivate_applies_before_canonical_relay"] = ServerDeactivateTransition,
        ["server_unlock_applies_before_canonical_relay"] = ServerUnlockTransition,
        ["server_queue_consumes_once_before_relay"] = ServerQueueTransition,
        ["server_transition_rejects_unknown_quest"] = ServerTransitionUnknown,
        ["server_transition_rejects_duplicate_state"] = ServerTransitionDuplicate,
        ["server_transition_rejects_invalid_player"] = ServerTransitionInvalidPlayer,
        ["server_transition_rejects_truncated_frame"] = ServerTransitionTruncated,
        ["server_transition_rejects_trailing_frame"] = ServerTransitionTrailing,
        ["server_transition_hook_failure_has_no_relay"] = ServerTransitionHookFailure,
        ["server_queue_missing_or_empty_is_noop"] = ServerQueueMissingEmpty,
        ["server_queue_rejects_invalid_player"] = ServerQueueInvalidPlayer,
        ["server_queue_rejects_truncated_frame"] = ServerQueueTruncated,
        ["server_queue_rejects_trailing_frame"] = ServerQueueTrailing,
        ["client_transitions_apply_without_echo"] = ClientTransitionsNoEcho,
        ["client_queue_removal_is_safe_and_silent"] = ClientQueueSafe,
        ["server_book_unlock_applies_before_canonical_relay"] = ServerBookUnlock,
        ["server_book_rejects_invalid_duplicate_and_trailing"] = ServerBookRejects,
        ["server_book_hook_failure_has_no_relay"] = ServerBookHookFailure,
        ["client_book_unlock_is_silent_and_idempotent"] = ClientBookUnlock,
        ["client_npc_loot_validates_index_and_frame"] = ClientNpcLootValidation,
		["nested_branch_debounce_tracks_entire_path"] = NestedBranchDebounceTracksEntirePath,
		["nested_local_frame_carries_complete_path"] = NestedLocalFrameCarriesCompletePath,
		["nested_local_completion_commits_resolved_leaf"] = NestedLocalCompletionCommitsResolvedLeaf,
		["nested_server_applies_exact_path"] = NestedServerAppliesExactPath,
		["nested_server_rejects_incomplete_path"] = NestedServerRejectsIncompletePath,
		["nested_server_rejects_overlong_path"] = NestedServerRejectsOverlongPath,
		["nested_server_rejects_sentinel_segment"] = NestedServerRejectsSentinelSegment,
		["nested_client_applies_exact_path_silently"] = NestedClientAppliesExactPathSilently,
		["nested_server_relay_preserves_complete_path"] = NestedServerRelayPreservesCompletePath,
		["progress_rejects_truncated_branch_path"] = ProgressRejectsTruncatedBranchPath,
		["completion_deactivate_failure_restores_task_graph"] = CompletionDeactivateFailureRestoresTaskGraph,
		["completion_successor_failure_restores_task_graph"] = CompletionSuccessorFailureRestoresTaskGraph,
		["completion_quest_hook_failure_restores_flags"] = CompletionQuestHookFailureRestoresFlags,
		["server_progress_failure_rolls_back_without_relay"] = ServerProgressFailureRollsBackWithoutRelay,
		["task_buffer_deactivate_failure_restores_graph"] = TaskBufferDeactivateFailureRestoresGraph,
		["task_buffer_activate_failure_restores_graph"] = TaskBufferActivateFailureRestoresGraph,
		["server_activate_post_hook_rolls_back"] = ServerActivatePostHookRollsBack,
		["server_deactivate_post_hook_rolls_back"] = ServerDeactivatePostHookRollsBack,
		["server_unlock_post_hook_rolls_back"] = ServerUnlockPostHookRollsBack,
		["book_post_hook_rolls_back"] = BookPostHookRollsBack,
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

    private static ProbeQuest Quest(params ProbeTask[] tasks)
    {
        for (int i = 0; i + 1 < tasks.Length; i++) tasks[i].NextTask = tasks[i + 1];
        var quest = new ProbeQuest();
        quest.Configure(tasks, tasks.FirstOrDefault());
        QuestManager.Quests.Add(quest);
        return quest;
    }

    private static BinaryReader Reader(Action<BinaryWriter> write)
    {
        var stream = new MemoryStream();
        using (var writer = new BinaryWriter(stream, System.Text.Encoding.UTF8, true)) write(writer);
        stream.Position = 0;
        return new BinaryReader(stream);
    }

    private static BinaryReader ProgressReader(Quest quest, byte slot, byte player)
		=> ProgressPathReader(quest, slot == byte.MaxValue ? Array.Empty<byte>() : new[] { slot }, player);

	private static BinaryReader ProgressPathReader(Quest quest, byte[] path, byte player)
		=> Reader(writer =>
		{
			writer.Write(quest.QuestName);
			writer.Write(quest.CurrentTask.TaskID);
			writer.Write((byte)path.Length);
			writer.Write(path);
			writer.Write(player);
		});

    private static void CompletionRequiresThree()
    {
        var task = new ProbeTask(1, true, true, true);
        ProbeQuest quest = Quest(task);
        quest.Update(); quest.Update();
        Check(!quest.IsCompleted && task.DeactivateCalls == 0, "advanced before third check");
        quest.Update();
        Check(quest.IsCompleted && task.DeactivateCalls == 1, "did not advance on third check");
    }

    private static void FalseResetsDebounce()
    {
        var task = new ProbeTask(1, true, true, false, true, true, true);
        ProbeQuest quest = Quest(task);
        for (int i = 0; i < 5; i++) quest.Update();
        Check(!quest.IsCompleted, "non-consecutive positives advanced quest");
        quest.Update();
        Check(quest.IsCompleted, "three checks after reset did not advance");
    }

    private static void TransitionResetsDebounce()
    {
        var first = new ProbeTask(1, true, true, true);
        var second = new ProbeTask(2, true, true, true);
        ProbeQuest quest = Quest(first, second);
        quest.Update(); quest.Update(); quest.Update();
        Check(ReferenceEquals(quest.CurrentTask, second), "first task did not transition");
        quest.Update(); quest.Update();
        Check(!quest.IsCompleted, "counter leaked into second task");
        quest.Update();
        Check(quest.IsCompleted, "second task did not get its own debounce");
    }

    private static void BranchIdentityRestartsDebounce()
    {
        var first = new ProbeTask(10, true, false, false, false);
        var successor = new ProbeTask(30);
        var second = new ProbeTask(11, true, true, true) { NextTask = successor };
        var branch = new BranchingTask(first, second) { TaskID = 1 };
        var quest = new ProbeQuest();
        quest.Configure(new QuestTask[] { branch, first, second, successor }, branch);
        QuestManager.Quests.Add(quest);
        quest.Update(); quest.Update(); quest.Update();
        Check(ReferenceEquals(quest.CurrentTask, branch), "different branch identities shared a debounce count");
        quest.Update();
        Check(ReferenceEquals(quest.CurrentTask, successor) && second.Completed, "same branch identity did not reach three checks");
    }

    private static void BranchChoosesFirst()
    {
        var first = new ProbeTask(10, true);
        var second = new ProbeTask(11, true);
        var branch = new BranchingTask(first, second);
        Check(branch.CheckCompletion(), "branch should complete");
        Check(branch.taskSlotForMP == 0, "did not choose first candidate");
        Check(second.CheckCalls == 0, "evaluated candidates after the first match");
    }

    private static void BranchRemembersSlot()
    {
        var successor = new ProbeTask(20);
        var first = new ProbeTask(10, false);
        var second = new ProbeTask(11, true) { NextTask = successor };
        var branch = new BranchingTask(first, second);
        Check(branch.CheckCompletion(), "branch did not complete");
        Check(branch.taskSlotForMP == 1 && ReferenceEquals(branch.NextTask, successor), "slot/successor mismatch");
    }

    private static void BranchResetClears()
    {
        var child = new ProbeTask(1, true) { Completed = true, NextTask = new ProbeTask(2) };
        var branch = new BranchingTask(child);
        branch.CheckCompletion(); branch.ResetProgress();
        Check(branch.taskSlotForMP == byte.MaxValue && branch.NextTask == null, "branch choice survived reset");
        Check(!child.Completed && child.ResetCalls == 1, "child did not reset");
    }

    private static void BranchRejectsUnrepresentableSlot()
    {
        var tasks = Enumerable.Range(0, 256).Select(i => new ProbeTask(i, i == 255)).Cast<QuestTask>().ToArray();
        Expect<ArgumentOutOfRangeException>(() => new BranchingTask(tasks));
    }

    private static void BranchConstructorSnapshotsInput()
    {
        var first = new ProbeTask(1, true);
        var replacement = new ProbeTask(2, true);
        QuestTask[] input = { first };
        var branch = new BranchingTask(input);
        input[0] = replacement;
        Check(branch.Tasks.Single() == first && branch.CheckCompletion() && branch.taskSlotForMP == 0, "caller mutation changed branch topology");
        Check(first.CheckCalls == 1 && replacement.CheckCalls == 0, "branch used caller-owned array");
    }

    private static void BranchRejectsNullChild()
    {
        Expect<ArgumentException>(() => new BranchingTask(new QuestTask[] { new ProbeTask(1), null }));
    }

    private static void BranchDeactivateWithoutChoice()
    {
        var first = new ProbeTask(1);
        var second = new ProbeTask(2);
        var branch = new BranchingTask(first, second);
        branch.Deactivate();
        Check(first.DeactivateCalls == 1 && second.DeactivateCalls == 1, "unselected active branch children were not deactivated");
    }

    private static void BranchDeactivateDuringPendingChoice()
    {
        var first = new ProbeTask(1, false);
        var second = new ProbeTask(2, true);
        var branch = new BranchingTask(first, second);
        Check(branch.CheckCompletion() && branch.taskSlotForMP == 1, "pending branch choice missing");
        branch.Deactivate();
        Check(first.DeactivateCalls == 1 && second.DeactivateCalls == 1, "pending debounce choice leaked an active child");
    }

    private static void LocalSendsBeforeMutation()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient; Terraria.Main.myPlayer = 3;
        var task = new ProbeTask(1);
        ProbeQuest quest = Quest(task);
        task.OnDeactivate = () =>
        {
            Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 1, "packet was not created before mutation");
            Check(global::SpiritMod.SpiritMod.Instance.Packets[0].Sent, "packet was not sent before mutation");
            Check(task.Completed, "deactivation did not follow completion marking");
        };
        quest.Complete();
        Check(quest.IsCompleted, "quest did not complete");
    }

	private static void LocalNonBranchEmptyPath()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient; Terraria.Main.myPlayer = 4;
        ProbeQuest quest = Quest(new ProbeTask(1));
        quest.Complete();
        using var reader = new BinaryReader(new MemoryStream(global::SpiritMod.SpiritMod.Instance.Packets.Single().ToArray()));
        Check(reader.ReadByte() == (byte)QuestMessageType.ProgressOrComplete, "message type");
        Check(reader.ReadBoolean(), "forServer flag");
        Check(reader.ReadString() == quest.QuestName, "quest name");
        Check(reader.ReadInt32() == 1, "task identity");
		Check(reader.ReadByte() == 0 && reader.ReadByte() == 4, "empty path/player");
    }

    private static void LocalBranchSelectedOnly()
    {
        var first = new ProbeTask(10, false, false, false);
        var successor = new ProbeTask(30);
        var second = new ProbeTask(11, true, true, true) { NextTask = successor };
        var branch = new BranchingTask(first, second) { TaskID = 1 };
        var quest = new ProbeQuest();
        quest.Configure(new QuestTask[] { branch, first, second, successor }, branch);
        QuestManager.Quests.Add(quest);
        quest.Update(); quest.Update(); quest.Update();
        Check(branch.Completed && second.Completed && second.DeactivateCalls == 1, "selected local branch was not completed once");
        Check(!first.Completed && first.DeactivateCalls == 0, "unselected local branch was mutated");
        Check(ReferenceEquals(quest.CurrentTask, successor) && successor.ActivateCalls == 1, "local branch successor mismatch");
    }

    private static void LocalBranchWrapperIdentity()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient;
        var x = BranchQuest();
        x.second.SetChecks(true);
        Check(x.branch.CheckCompletion(), "branch did not choose child");
        x.quest.Complete();
        using var reader = new BinaryReader(new MemoryStream(global::SpiritMod.SpiritMod.Instance.Packets.Single().ToArray()));
        reader.ReadByte(); reader.ReadBoolean(); reader.ReadString();
		Check(reader.ReadInt32() == x.branch.TaskID && reader.ReadByte() == 1 && reader.ReadByte() == 1, "progress frame lost wrapper identity or child path");
    }

    private static void QuietNeverEchoes()
    {
        Terraria.Main.netMode = NetmodeID.MultiplayerClient;
        ProbeQuest quest = Quest(new ProbeTask(1));
        QuestManager.Quiet = true;
        quest.Complete();
        Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "quiet application echoed a frame");
    }

    private static (ProbeQuest quest, BranchingTask branch, ProbeTask first, ProbeTask second, ProbeTask successor) BranchQuest()
    {
        var first = new ProbeTask(10);
        var successor = new ProbeTask(30);
        var second = new ProbeTask(11) { NextTask = successor };
        var branch = new BranchingTask(first, second) { TaskID = 1 };
        var quest = new ProbeQuest();
        quest.Configure(new QuestTask[] { branch, first, second, successor }, branch);
        QuestManager.Quests.Add(quest);
        return (quest, branch, first, second, successor);
    }

    private static void RemoteBranchSelectedChild()
    {
        var x = BranchQuest(); QuestManager.Quiet = true;
        x.quest.Complete(1);
        Check(x.second.Completed && x.second.DeactivateCalls == 1, "selected child not completed exactly once");
        Check(!x.first.Completed && x.first.DeactivateCalls == 0, "unselected child mutated");
    }

    private static void RemoteBranchSuccessor()
    {
        var x = BranchQuest(); QuestManager.Quiet = true;
        x.quest.Complete(1);
        Check(ReferenceEquals(x.quest.CurrentTask, x.successor), "wrong successor");
        Check(x.successor.ActivateCalls == 1, "successor not activated");
    }

    private static void RemoteInvalidBranchNoop()
    {
        var x = BranchQuest(); QuestManager.Quiet = true;
        x.quest.Complete(2);
        Check(ReferenceEquals(x.quest.CurrentTask, x.branch) && !x.first.Completed && !x.second.Completed, "invalid slot mutated state");
    }

    private static void RemoteStaleBranchNoop()
    {
        var task = new ProbeTask(1); ProbeQuest quest = Quest(task); QuestManager.Quiet = true;
        quest.Complete(0);
        Check(ReferenceEquals(quest.CurrentTask, task) && !task.Completed, "branch frame applied to nonbranch task");
    }

    private static void TaskBufferVariablePayload()
    {
        byte[] payload = Enumerable.Range(0, 80).Select(i => (byte)i).ToArray();
        var task = new ProbeTask(77) { Payload = payload };
        ProbeQuest quest = Quest(task);
        byte[] buffer = quest.GetTaskDataBuffer();
        Check(buffer.Length == 86 && BitConverter.ToUInt16(buffer, 4) == 80 && buffer.Skip(6).SequenceEqual(payload), "payload frame mismatch");
    }

    private static void TaskBufferZeroPayload()
    {
        ProbeQuest quest = Quest(new ProbeTask(9) { Payload = Array.Empty<byte>() });
        byte[] buffer = quest.GetTaskDataBuffer();
        Check(buffer.Length == 6 && BitConverter.ToInt32(buffer) == 9 && BitConverter.ToUInt16(buffer, 4) == 0, "zero payload framing wrong");
    }

    private static void TaskBufferSwitchAfterRead()
    {
        var oldTask = new ProbeTask(1);
        var target = new ProbeTask(2) { ReadLength = 3 };
        var quest = new ProbeQuest(); quest.Configure(new QuestTask[] { oldTask, target }, oldTask);
        quest.ReadFromDataBuffer(new byte[] { 2, 0, 0, 0, 3, 0, 8, 9, 10 });
        Check(ReferenceEquals(quest.CurrentTask, target), "did not switch task");
        Check(oldTask.DeactivateCalls == 1 && target.ActivateCalls == 1, "transition hooks wrong");
        Check(target.Payload.SequenceEqual(new byte[] { 8, 9, 10 }), "payload not read");
    }

    private static void TaskBufferShortHeader()
    {
        var current = new ProbeTask(1); ProbeQuest quest = Quest(current);
        RejectMalformed(() => quest.ReadFromDataBuffer(new byte[] { 1, 0, 0 }));
        Check(ReferenceEquals(quest.CurrentTask, current) && current.DeactivateCalls == 0, "short frame replaced state");
    }

    private static void TaskBufferUnknownId()
    {
        var current = new ProbeTask(1); ProbeQuest quest = Quest(current);
        RejectMalformed(() => quest.ReadFromDataBuffer(new byte[] { 231, 3, 0, 0, 0, 0 }));
        Check(ReferenceEquals(quest.CurrentTask, current) && current.DeactivateCalls == 0, "unknown task replaced state");
    }

    private static void TaskBufferTruncated()
    {
        var current = new ProbeTask(1); var target = new ProbeTask(2) { ReadLength = 4 };
        var quest = new ProbeQuest(); quest.Configure(new QuestTask[] { current, target }, current);
        RejectMalformed(() => quest.ReadFromDataBuffer(new byte[] { 2, 0, 0, 0, 4, 0, 1, 2 }));
        Check(ReferenceEquals(quest.CurrentTask, current) && current.DeactivateCalls == 0 && target.ActivateCalls == 0, "truncated frame replaced state");
    }

    private static void TaskBufferTrailing()
    {
        var current = new ProbeTask(1);
        var target = new ProbeTask(2) { Payload = new byte[] { 9 } };
        var quest = new ProbeQuest(); quest.Configure(new QuestTask[] { current, target }, current);
        RejectMalformed(() => quest.ReadFromDataBuffer(new byte[] { 2, 0, 0, 0, 1, 0, 7, 8 }));
        Check(ReferenceEquals(quest.CurrentTask, current) && target.Payload.SequenceEqual(new byte[] { 9 }), "trailing frame mutated target/current task");
    }

    private static void TaskBufferRollback()
    {
        var current = new ProbeTask(1);
        var target = new ProbeTask(2) { Payload = new byte[] { 9 }, ThrowsAfterRead = 1 };
        var quest = new ProbeQuest(); quest.Configure(new QuestTask[] { current, target }, current);
        RejectMalformed(() => quest.ReadFromDataBuffer(new byte[] { 2, 0, 0, 0, 2, 0, 7, 8 }));
        Check(ReferenceEquals(quest.CurrentTask, current) && target.Payload.SequenceEqual(new byte[] { 9 }), "failed read leaked target task state");
        Check(current.DeactivateCalls == 0 && target.ActivateCalls == 0, "failed read ran lifecycle hooks");
    }

    private static void TaskBufferSameTaskNoLifecycle()
    {
        var current = new ProbeTask(1) { Payload = new byte[] { 3 } };
        ProbeQuest quest = Quest(current);
        quest.ReadFromDataBuffer(new byte[] { 1, 0, 0, 0, 2, 0, 7, 8 });
        Check(current.Payload.SequenceEqual(new byte[] { 7, 8 }), "same-task payload not applied");
        Check(current.ActivateCalls == 0 && current.DeactivateCalls == 0, "same-task snapshot replayed lifecycle hooks");
    }

    private static void TaskBufferOversize()
    {
        ProbeQuest quest = Quest(new ProbeTask(1) { Payload = new byte[ushort.MaxValue + 1] });
        Expect<InvalidDataException>(() => quest.GetTaskDataBuffer());
    }

    private static byte[] SerializeTaskData(QuestTask task)
    {
        using var stream = new MemoryStream();
        using (var writer = new BinaryWriter(stream, System.Text.Encoding.UTF8, true)) task.WriteData(writer);
        return stream.ToArray();
    }

    private static void BranchDataRoundtrip()
    {
        var successor = new ProbeTask(30);
        var first = new ProbeTask(10) { Payload = new byte[] { 1, 2 }, Completed = true };
        var second = new ProbeTask(11, true) { Payload = new byte[] { 3, 4, 5 }, NextTask = successor };
        var source = new BranchingTask(first, second);
        source.CheckCompletion();
        byte[] frame = SerializeTaskData(source);

        var restoredFirst = new ProbeTask(10) { Payload = new byte[] { 8 } };
        var restoredSecond = new ProbeTask(11) { Payload = new byte[] { 9 }, NextTask = successor };
        var restored = new BranchingTask(restoredFirst, restoredSecond);
        using var reader = new BinaryReader(new MemoryStream(frame));
        restored.ReadData(reader);
        Check(restoredFirst.Completed && restoredFirst.Payload.SequenceEqual(new byte[] { 1, 2 }), "first branch child state lost");
        Check(!restoredSecond.Completed && restoredSecond.Payload.SequenceEqual(new byte[] { 3, 4, 5 }), "second branch child state lost");
        Check(restored.taskSlotForMP == 1 && ReferenceEquals(restored.NextTask, successor), "branch choice/successor not restored");
    }

    private static void BranchDataWrongVersion()
    {
        var child = new ProbeTask(10) { Payload = new byte[] { 9 } };
        var branch = new BranchingTask(child);
        byte[] frame = SerializeTaskData(new BranchingTask(new ProbeTask(10) { Payload = new byte[] { 1 } }));
        frame[0] = 2;
        using var reader = new BinaryReader(new MemoryStream(frame));
        RejectMalformed(() => branch.ReadData(reader));
        Check(child.Payload.SequenceEqual(new byte[] { 9 }) && branch.taskSlotForMP == byte.MaxValue, "version rejection mutated branch");
    }

    private static void BranchDataWrongTopology()
    {
        var child = new ProbeTask(10) { Payload = new byte[] { 9 } };
        var branch = new BranchingTask(child);
        byte[] frame = SerializeTaskData(new BranchingTask(new ProbeTask(10) { Payload = new byte[] { 1 } }));
        frame[1] = 0;
        using var reader = new BinaryReader(new MemoryStream(frame));
        RejectMalformed(() => branch.ReadData(reader));
        Check(child.Payload.SequenceEqual(new byte[] { 9 }) && branch.taskSlotForMP == byte.MaxValue, "topology rejection mutated branch");
    }

    private static void BranchDataTruncated()
    {
        var child = new ProbeTask(10) { Payload = new byte[] { 9 } };
        var branch = new BranchingTask(child);
        byte[] full = SerializeTaskData(new BranchingTask(new ProbeTask(10) { Payload = new byte[] { 1, 2 } }));
        byte[] truncated = full.Take(full.Length - 1).ToArray();
        using var reader = new BinaryReader(new MemoryStream(truncated));
        RejectMalformed(() => branch.ReadData(reader));
        Check(child.Payload.SequenceEqual(new byte[] { 9 }) && branch.taskSlotForMP == byte.MaxValue, "truncated branch frame mutated state");
    }

    private static void BranchDataRollback()
    {
        var source = new BranchingTask(
            new ProbeTask(10) { Payload = new byte[] { 1 } },
            new ProbeTask(11) { Payload = new byte[] { 2 } });
        byte[] frame = SerializeTaskData(source);
        var first = new ProbeTask(10) { Payload = new byte[] { 8 } };
        var second = new ProbeTask(11) { Payload = new byte[] { 9 }, ThrowsAfterRead = 1 };
        var target = new BranchingTask(first, second);
        using var reader = new BinaryReader(new MemoryStream(frame));
        RejectMalformed(() => target.ReadData(reader));
        Check(first.Payload.SequenceEqual(new byte[] { 8 }) && second.Payload.SequenceEqual(new byte[] { 9 }), "partial child read was not rolled back");
        Check(target.taskSlotForMP == byte.MaxValue && target.NextTask == null, "failed branch read changed selection");
    }

    private static (StoredQuestData data, byte[] frame) Snapshot(StoredQuestData stored)
    {
        ProbeQuest quest = Quest(new ProbeTask(1)); QuestWorld.Store = _ => stored;
        var packet = new ModPacket(); QuestMultiplayer.WriteQuestToPacket(packet, quest);
        byte[] frame = packet.ToArray();
        using var reader = new BinaryReader(new MemoryStream(frame));
        reader.ReadString(); long flags = reader.ReadInt64();
        return (QuestMultiplayer.ReadQuestFromLong(flags), frame);
    }

    private static void SnapshotBooleanRoundtrip()
    {
        StoredQuestData decoded = Snapshot(new StoredQuestData { IsUnlocked=true, IsActive=true, IsCompleted=true, RewardsGiven=true }).data;
        Check(decoded.IsUnlocked && decoded.IsActive && decoded.IsCompleted && decoded.RewardsGiven, "boolean flags lost");
        decoded = Snapshot(new StoredQuestData()).data;
        Check(!decoded.IsUnlocked && !decoded.IsActive && !decoded.IsCompleted && !decoded.RewardsGiven, "boolean flags leaked");
    }

    private static void SnapshotSignedRoundtrip()
    {
        foreach ((short active, short unlocked) in new[] { ((short)-1,(short)2), (short.MinValue,short.MaxValue), ((short)1234,(short)-2345) })
        {
            StoredQuestData decoded = Snapshot(new StoredQuestData { TimeLeftActive=active, TimeLeftUnlocked=unlocked, IsUnlocked=true }).data;
            Check(decoded.TimeLeftActive == active && decoded.TimeLeftUnlocked == unlocked && decoded.IsUnlocked, $"signed fields corrupted: {active}/{unlocked}");
        }
    }

    private static void SnapshotZeroBuffer()
    {
        byte[] frame = Snapshot(new StoredQuestData { Buffer = Array.Empty<byte>() }).frame;
        using var reader = new BinaryReader(new MemoryStream(frame)); reader.ReadString(); reader.ReadInt64();
        Check(reader.ReadByte() == 0 && reader.BaseStream.Position == reader.BaseStream.Length, "zero buffer framing");
    }

    private static void SnapshotMaxBuffer()
    {
        byte[] payload = Enumerable.Range(0, 255).Select(i => (byte)i).ToArray();
        byte[] frame = Snapshot(new StoredQuestData { Buffer = payload }).frame;
        using var reader = new BinaryReader(new MemoryStream(frame)); reader.ReadString(); reader.ReadInt64();
        int length = reader.ReadByte(); byte[] actual = reader.ReadBytes(length);
        Check(length == 255 && actual.SequenceEqual(payload) && reader.BaseStream.Position == reader.BaseStream.Length, "255-byte frame mismatch");
    }

    private static void SnapshotOversizeRejected()
    {
        ProbeQuest quest = Quest(new ProbeTask(1)); QuestWorld.Store = _ => new StoredQuestData { Buffer = new byte[256] };
        var packet = new ModPacket(); Expect<InvalidDataException>(() => QuestMultiplayer.WriteQuestToPacket(packet, quest));
        Check(packet.ToArray().Length == 0, "partial ambiguous frame emitted");
    }

    private static void ServerRejectsUnknownQuest()
    {
		using var reader = Reader(w => { w.Write("missing"); w.Write(1); w.Write((byte)0); w.Write((byte)1); });
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, true);
        Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "unknown quest relayed");
    }

    private static void ServerRejectsInvalidPlayer()
    {
        ProbeQuest quest = Quest(new ProbeTask(1));
        using var reader = ProgressReader(quest, byte.MaxValue, (byte)Terraria.Main.maxPlayers);
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, true);
        Check(!quest.IsCompleted && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "invalid player applied/relayed");
    }

    private static void ServerRejectsInvalidBranch()
    {
        var x = BranchQuest();
        using var reader = ProgressReader(x.quest, 7, 1);
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, true);
        Check(ReferenceEquals(x.quest.CurrentTask, x.branch) && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "invalid branch applied/relayed");
    }

    private static void ServerRejectsNonBranchSlot()
    {
        ProbeTask task = new(1); ProbeQuest quest = Quest(task);
        using var reader = ProgressReader(quest, 0, 1);
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, true);
        Check(!task.Completed && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "stale slot applied/relayed");
    }

    private static void ServerAppliesBeforeRelay()
    {
        ProbeTask task = new(1); ProbeQuest quest = Quest(task);
        task.OnDeactivate = () => Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "relayed before authoritative apply");
        using var reader = ProgressReader(quest, byte.MaxValue, 2);
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, true);
        Check(task.DeactivateCalls == 1 && global::SpiritMod.SpiritMod.Instance.Packets.Count == 1, "not applied/relayed exactly once");
    }

    private static void ServerRelayCanonical()
    {
        ProbeQuest quest = Quest(new ProbeTask(1));
        using var input = ProgressReader(quest, byte.MaxValue, 3);
        QuestMultiplayer.HandlePacket(input, QuestMessageType.ProgressOrComplete, true);
        ModPacket packet = global::SpiritMod.SpiritMod.Instance.Packets.Single();
        Check(packet.Sent && packet.ToClient == -1 && packet.IgnoreClient == 3, "sender exclusion wrong");
        using var reader = new BinaryReader(new MemoryStream(packet.ToArray()));
        Check(reader.ReadByte() == (byte)QuestMessageType.ProgressOrComplete && !reader.ReadBoolean(), "canonical header wrong");
		Check(reader.ReadString() == quest.QuestName && reader.ReadInt32() == 1 && reader.ReadByte() == 0, "canonical payload wrong");
        Check(reader.BaseStream.Position == reader.BaseStream.Length, "claimed player leaked into relay");
    }

    private static void ClientAppliesWithoutEcho()
    {
        ProbeTask task = new(1); ProbeQuest quest = Quest(task);
		using var reader = Reader(w => { w.Write(quest.QuestName); w.Write(task.TaskID); w.Write((byte)0); });
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, false);
        Check(task.Completed && task.DeactivateCalls == 1 && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "client application echoed or failed");
    }

    private static void ServerRejectsStaleTask()
    {
        ProbeTask task = new(1); ProbeQuest quest = Quest(task);
		using var reader = Reader(w => { w.Write(quest.QuestName); w.Write(99); w.Write((byte)0); w.Write((byte)1); });
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, true);
        Check(!task.Completed && task.DeactivateCalls == 0 && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "stale server task identity advanced current task");
    }

    private static void ClientRejectsStaleTask()
    {
        ProbeTask task = new(1); ProbeQuest quest = Quest(task);
		using var reader = Reader(w => { w.Write(quest.QuestName); w.Write(99); w.Write((byte)0); });
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, false);
        Check(!task.Completed && task.DeactivateCalls == 0 && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "stale client task identity advanced current task");
    }

    private static void ServerProgressTrailing()
    {
        ProbeTask task = new(1); ProbeQuest quest = Quest(task);
		using var reader = Reader(w => { w.Write(quest.QuestName); w.Write(task.TaskID); w.Write((byte)0); w.Write((byte)1); w.Write((byte)7); });
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, true);
        Check(!task.Completed && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "server accepted progress frame with trailing data");
    }

    private static void ClientProgressTrailing()
    {
        ProbeTask task = new(1); ProbeQuest quest = Quest(task);
		using var reader = Reader(w => { w.Write(quest.QuestName); w.Write(task.TaskID); w.Write((byte)0); w.Write((byte)7); });
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, false);
        Check(!task.Completed && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "client accepted progress frame with trailing data");
    }

    private static void CompletionRestoresQuiet()
    {
        ProbeQuest quest = Quest(new ProbeTask(1)); QuestManager.Quiet = true;
        QuestMultiplayer.CompleteQuestOrTask(quest.QuestName, byte.MaxValue);
        Check(QuestManager.Quiet, "prior true quiet state was discarded");
    }

    private static void CompletionRestoresOnThrow()
    {
        ProbeTask task = new(1) { ThrowOnDeactivate = true }; ProbeQuest quest = Quest(task);
        Expect<InvalidOperationException>(() => QuestMultiplayer.CompleteQuestOrTask(quest.QuestName, byte.MaxValue));
        Check(!QuestManager.Quiet, "quiet leaked after task exception");
    }

    private static void ActivateRestoresOnThrow()
    {
        ProbeQuest quest = Quest(new ProbeTask(1)); QuestManager.BeforeActivate = _ => throw new InvalidOperationException("boom");
        Expect<InvalidOperationException>(() => QuestMultiplayer.ActivateQuest(quest.QuestName));
        Check(!QuestManager.Quiet, "activate leaked quiet");
    }

    private static void OtherHelpersRestoreQuiet()
    {
        ProbeQuest quest = Quest(new ProbeTask(1)); QuestManager.Quiet = true;
        QuestMultiplayer.DeactivateQuest(quest.QuestName);
        Check(QuestManager.Quiet, "deactivate did not preserve prior quiet");
        QuestManager.Quiet = false; QuestManager.BeforeUnlock = _ => throw new InvalidOperationException("boom");
        Expect<InvalidOperationException>(() => QuestMultiplayer.UnlockQuest(quest.QuestName));
        Check(!QuestManager.Quiet, "unlock leaked quiet");
    }

    private static BinaryReader TransitionReader(string name, byte player)
        => Reader(w => { w.Write(name); w.Write(player); });

    private static BinaryReader QueueReader(ushort npcId, byte player)
        => Reader(w => { w.Write(npcId); w.Write(player); });

    private static void CheckTransitionRelay(QuestMessageType type, string name, int ignoredPlayer)
    {
        ModPacket packet = global::SpiritMod.SpiritMod.Instance.Packets.Single();
        Check(packet.Sent && packet.ToClient == -1 && packet.IgnoreClient == ignoredPlayer, "transition relay destination");
        using var reader = new BinaryReader(new MemoryStream(packet.ToArray()));
        Check(reader.ReadByte() == (byte)type && !reader.ReadBoolean(), "transition relay header");
        Check(reader.ReadString() == name && reader.BaseStream.Position == reader.BaseStream.Length, "transition relay payload");
    }

    private static void ServerActivateTransition()
    {
        ProbeQuest quest = Quest(new ProbeTask(1));
        QuestManager.BeforeActivate = _ => Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "activation relayed before apply");
        using var reader = TransitionReader(quest.QuestName, 2);
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.Activate, true);
        Check(quest.IsActive && QuestManager.ActivateCalls == 1 && !QuestManager.Quiet, "activation not applied exactly once");
        CheckTransitionRelay(QuestMessageType.Activate, quest.QuestName, 2);
    }

    private static void ServerDeactivateTransition()
    {
        ProbeQuest quest = Quest(new ProbeTask(1)); quest.IsActive = true;
        QuestManager.BeforeDeactivate = _ => Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "deactivation relayed before apply");
        using var reader = TransitionReader(quest.QuestName, 3);
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.Deactivate, true);
        Check(!quest.IsActive && QuestManager.DeactivateCalls == 1 && !QuestManager.Quiet, "deactivation not applied exactly once");
        CheckTransitionRelay(QuestMessageType.Deactivate, quest.QuestName, 3);
    }

    private static void ServerUnlockTransition()
    {
        ProbeQuest quest = Quest(new ProbeTask(1));
        QuestManager.BeforeUnlock = _ => Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "unlock relayed before apply");
        using var reader = TransitionReader(quest.QuestName, 4);
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.Unlock, true);
        Check(quest.IsUnlocked && QuestManager.UnlockCalls == 1 && !QuestManager.Quiet, "unlock not applied exactly once");
        CheckTransitionRelay(QuestMessageType.Unlock, quest.QuestName, 4);
    }

    private static void ServerQueueTransition()
    {
        var queues = ModContent.GetInstance<QuestWorld>().NPCQuestQueue;
        queues[25] = new Queue<int>(new[] { 7, 8 }); queues[26] = new Queue<int>(new[] { 9 });
        using var reader = QueueReader(25, 2);
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.SyncNPCQueue, true);
        Check(queues[25].SequenceEqual(new[] { 8 }) && queues[26].SequenceEqual(new[] { 9 }), "wrong queue mutation");
        ModPacket packet = global::SpiritMod.SpiritMod.Instance.Packets.Single();
        Check(packet.Sent && packet.ToClient == -1 && packet.IgnoreClient == 2, "queue relay destination");
        using var relay = new BinaryReader(new MemoryStream(packet.ToArray()));
        Check(relay.ReadByte() == (byte)QuestMessageType.SyncNPCQueue && !relay.ReadBoolean(), "queue relay header");
        Check(relay.ReadUInt16() == 25 && relay.BaseStream.Position == relay.BaseStream.Length, "queue relay payload");
    }

    private static void ServerTransitionUnknown()
    {
        foreach (QuestMessageType type in new[] { QuestMessageType.Activate, QuestMessageType.Deactivate, QuestMessageType.Unlock })
        {
            using var reader = TransitionReader("missing", 1);
            QuestMultiplayer.HandlePacket(reader, type, true);
        }
        Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "unknown transition relayed");
        Check(QuestManager.ActivateCalls + QuestManager.DeactivateCalls + QuestManager.UnlockCalls == 0, "unknown transition applied");
    }

    private static void ServerTransitionDuplicate()
    {
        ProbeQuest quest = Quest(new ProbeTask(1));
        quest.IsActive = true;
        using (var reader = TransitionReader(quest.QuestName, 1)) QuestMultiplayer.HandlePacket(reader, QuestMessageType.Activate, true);
        quest.IsActive = false;
        using (var reader = TransitionReader(quest.QuestName, 1)) QuestMultiplayer.HandlePacket(reader, QuestMessageType.Deactivate, true);
        quest.IsUnlocked = true;
        using (var reader = TransitionReader(quest.QuestName, 1)) QuestMultiplayer.HandlePacket(reader, QuestMessageType.Unlock, true);
        Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0 && QuestManager.ActivateCalls + QuestManager.DeactivateCalls + QuestManager.UnlockCalls == 0, "duplicate transition was applied or relayed");
    }

    private static void ServerTransitionInvalidPlayer()
    {
        ProbeQuest quest = Quest(new ProbeTask(1));
        using (var reader = TransitionReader(quest.QuestName, (byte)Terraria.Main.maxPlayers)) QuestMultiplayer.HandlePacket(reader, QuestMessageType.Activate, true);
        quest.IsActive = true;
        using (var reader = TransitionReader(quest.QuestName, (byte)Terraria.Main.maxPlayers)) QuestMultiplayer.HandlePacket(reader, QuestMessageType.Deactivate, true);
        using (var reader = TransitionReader(quest.QuestName, (byte)Terraria.Main.maxPlayers)) QuestMultiplayer.HandlePacket(reader, QuestMessageType.Unlock, true);
        Check(quest.IsActive && !quest.IsUnlocked && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "invalid player changed transition state");
        Check(QuestManager.ActivateCalls + QuestManager.DeactivateCalls + QuestManager.UnlockCalls == 0, "invalid player called manager");
    }

    private static void ServerTransitionTruncated()
    {
        ProbeQuest quest = Quest(new ProbeTask(1));
        foreach (QuestMessageType type in new[] { QuestMessageType.Activate, QuestMessageType.Deactivate, QuestMessageType.Unlock })
        {
            using var reader = Reader(w => w.Write(quest.QuestName));
            RejectMalformed(() => QuestMultiplayer.HandlePacket(reader, type, true));
        }
        Check(!quest.IsActive && !quest.IsUnlocked && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "truncated transition applied or relayed");
        Check(QuestManager.ActivateCalls + QuestManager.DeactivateCalls + QuestManager.UnlockCalls == 0, "truncated transition called manager");
    }

    private static void ServerTransitionTrailing()
    {
        ProbeQuest quest = Quest(new ProbeTask(1));
        using var reader = Reader(w => { w.Write(quest.QuestName); w.Write((byte)1); w.Write((byte)7); });
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.Activate, true);
        Check(!quest.IsActive && QuestManager.ActivateCalls == 0 && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "transition accepted trailing data");
    }

    private static void ServerTransitionHookFailure()
    {
        ProbeQuest quest = Quest(new ProbeTask(1));
        QuestManager.BeforeActivate = _ => throw new InvalidOperationException("activation hook");
        using (var reader = TransitionReader(quest.QuestName, 1)) RejectMalformed(() => QuestMultiplayer.HandlePacket(reader, QuestMessageType.Activate, true));
        QuestManager.BeforeActivate = null; quest.IsActive = true;
        QuestManager.BeforeDeactivate = _ => throw new InvalidOperationException("deactivation hook");
        using (var reader = TransitionReader(quest.QuestName, 1)) RejectMalformed(() => QuestMultiplayer.HandlePacket(reader, QuestMessageType.Deactivate, true));
        QuestManager.BeforeDeactivate = null;
        QuestManager.BeforeUnlock = _ => throw new InvalidOperationException("unlock hook");
        using (var reader = TransitionReader(quest.QuestName, 1)) RejectMalformed(() => QuestMultiplayer.HandlePacket(reader, QuestMessageType.Unlock, true));
        Check(QuestManager.ActivateCalls == 1 && QuestManager.DeactivateCalls == 1 && QuestManager.UnlockCalls == 1, "valid transition hook not invoked");
        Check(!QuestManager.Quiet && quest.IsActive && !quest.IsUnlocked && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "hook failure leaked quiet or relay");
    }

    private static void ServerQueueMissingEmpty()
    {
        var queues = ModContent.GetInstance<QuestWorld>().NPCQuestQueue; queues[25] = new Queue<int>();
        using (var reader = QueueReader(24, 1)) QuestMultiplayer.HandlePacket(reader, QuestMessageType.SyncNPCQueue, true);
        using (var reader = QueueReader(25, 1)) QuestMultiplayer.HandlePacket(reader, QuestMessageType.SyncNPCQueue, true);
        Check(queues[25].Count == 0 && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "missing/empty queue relayed");
    }

    private static void ServerQueueInvalidPlayer()
    {
        var queues = ModContent.GetInstance<QuestWorld>().NPCQuestQueue; queues[25] = new Queue<int>(new[] { 7 });
        using var reader = QueueReader(25, (byte)Terraria.Main.maxPlayers);
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.SyncNPCQueue, true);
        Check(queues[25].SequenceEqual(new[] { 7 }) && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "invalid queue player applied or relayed");
    }

    private static void ServerQueueTruncated()
    {
        var queues = ModContent.GetInstance<QuestWorld>().NPCQuestQueue; queues[25] = new Queue<int>(new[] { 7 });
        using var reader = Reader(w => w.Write((ushort)25));
        RejectMalformed(() => QuestMultiplayer.HandlePacket(reader, QuestMessageType.SyncNPCQueue, true));
        Check(queues[25].SequenceEqual(new[] { 7 }) && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "truncated queue frame applied or relayed");
    }

    private static void ServerQueueTrailing()
    {
        var queues = ModContent.GetInstance<QuestWorld>().NPCQuestQueue; queues[25] = new Queue<int>(new[] { 7 });
        using var reader = Reader(w => { w.Write((ushort)25); w.Write((byte)1); w.Write((byte)9); });
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.SyncNPCQueue, true);
        Check(queues[25].SequenceEqual(new[] { 7 }) && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "queue frame with trailing data applied or relayed");
    }

    private static void ClientTransitionsNoEcho()
    {
        ProbeQuest quest = Quest(new ProbeTask(1));
        using (var reader = Reader(w => w.Write(quest.QuestName))) QuestMultiplayer.HandlePacket(reader, QuestMessageType.Activate, false);
        Check(quest.IsActive, "client activation missing");
        using (var reader = Reader(w => w.Write(quest.QuestName))) QuestMultiplayer.HandlePacket(reader, QuestMessageType.Deactivate, false);
        Check(!quest.IsActive, "client deactivation missing");
        using (var reader = Reader(w => w.Write(quest.QuestName))) QuestMultiplayer.HandlePacket(reader, QuestMessageType.Unlock, false);
        Check(quest.IsUnlocked && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "client unlock failed or echoed");
    }

    private static void ClientQueueSafe()
    {
        var queues = ModContent.GetInstance<QuestWorld>().NPCQuestQueue;
        queues[25] = new Queue<int>(new[] { 7, 8 }); queues[26] = new Queue<int>();
        foreach (ushort npcId in new ushort[] { 25, 26, 27 })
        {
            using var reader = Reader(w => w.Write(npcId));
            QuestMultiplayer.HandlePacket(reader, QuestMessageType.SyncNPCQueue, false);
        }
        Check(queues[25].SequenceEqual(new[] { 8 }) && queues[26].Count == 0 && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "client queue removal not safe/silent");
    }

    private static void ServerBookUnlock()
    {
        QuestManager.BeforeUnlockQuestBook = () => Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "book relay preceded authoritative apply");
        using var reader = Reader(w => w.Write((byte)2));
        QuestMultiplayer.HandlePacket(reader, QuestMessageType.ObtainQuestBook, true);
        Check(QuestManager.QuestBookUnlocked && QuestManager.UnlockQuestBookCalls == 1, "book was not unlocked exactly once");
        ModPacket packet = global::SpiritMod.SpiritMod.Instance.Packets.Single();
        Check(packet.Sent && packet.ToClient == -1 && packet.IgnoreClient == 2, "book relay destination");
        using var relay = new BinaryReader(new MemoryStream(packet.ToArray()));
        Check(relay.ReadByte() == (byte)QuestMessageType.ObtainQuestBook && !relay.ReadBoolean() && relay.BaseStream.Position == relay.BaseStream.Length, "book relay was not canonical");
    }

    private static void ServerBookRejects()
    {
        using (var invalid = Reader(w => w.Write((byte)Terraria.Main.maxPlayers)))
            QuestMultiplayer.HandlePacket(invalid, QuestMessageType.ObtainQuestBook, true);
        using (var trailing = Reader(w => { w.Write((byte)1); w.Write((byte)7); }))
            QuestMultiplayer.HandlePacket(trailing, QuestMessageType.ObtainQuestBook, true);
        QuestManager.QuestBookUnlocked = true;
        using (var duplicate = Reader(w => w.Write((byte)1)))
            QuestMultiplayer.HandlePacket(duplicate, QuestMessageType.ObtainQuestBook, true);
        Check(QuestManager.UnlockQuestBookCalls == 0 && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "invalid, duplicate, or trailing book request applied/relayed");
    }

    private static void ServerBookHookFailure()
    {
        QuestManager.BeforeUnlockQuestBook = () => throw new InvalidOperationException("book hook");
        using var reader = Reader(w => w.Write((byte)1));
        RejectMalformed(() => QuestMultiplayer.HandlePacket(reader, QuestMessageType.ObtainQuestBook, true));
        Check(!QuestManager.QuestBookUnlocked && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "failed book hook changed state or relayed");
    }

    private static void ClientBookUnlock()
    {
        using (var first = Reader(_ => { })) QuestMultiplayer.HandlePacket(first, QuestMessageType.ObtainQuestBook, false);
        using (var duplicate = Reader(_ => { })) QuestMultiplayer.HandlePacket(duplicate, QuestMessageType.ObtainQuestBook, false);
        Check(QuestManager.QuestBookUnlocked && QuestManager.UnlockQuestBookCalls == 1, "client book relay was not idempotent");
        Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "client book relay echoed");
    }

    private static void ClientNpcLootValidation()
    {
        Terraria.Main.npc = new[] { new Terraria.NPC(), new Terraria.NPC() };
        QuestGlobalNPC global = ModContent.GetInstance<QuestGlobalNPC>();
        using (var valid = Reader(w => w.Write((byte)1))) QuestMultiplayer.HandlePacket(valid, QuestMessageType.SyncOnNPCLoot, false);
        using (var invalid = Reader(w => w.Write((byte)2))) QuestMultiplayer.HandlePacket(invalid, QuestMessageType.SyncOnNPCLoot, false);
        using (var trailing = Reader(w => { w.Write((byte)0); w.Write((byte)7); })) QuestMultiplayer.HandlePacket(trailing, QuestMessageType.SyncOnNPCLoot, false);
        Check(global.ClientLootCalls == 1 && ReferenceEquals(global.LastNPC, Terraria.Main.npc[1]), "NPC loot index/frame validation failed");
        Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "client NPC loot echoed");
    }

	private static (ProbeQuest quest, BranchingTask outer, ProbeTask outerAlternative, BranchingTask inner, ProbeTask firstLeaf, ProbeTask secondLeaf, ProbeTask successor) NestedQuest(bool[] firstChecks = null, bool[] secondChecks = null)
	{
		var outerAlternative = new ProbeTask(10, false);
		var successor = new ProbeTask(30);
		var firstLeaf = new ProbeTask(20, firstChecks ?? Array.Empty<bool>()) { NextTask = successor };
		var secondLeaf = new ProbeTask(21, secondChecks ?? Array.Empty<bool>()) { NextTask = successor };
		var inner = new BranchingTask(firstLeaf, secondLeaf) { TaskID = 11 };
		var outer = new BranchingTask(outerAlternative, inner) { TaskID = 1 };
		var quest = new ProbeQuest();
		quest.Configure(new QuestTask[] { outer, outerAlternative, inner, firstLeaf, secondLeaf, successor }, outer);
		QuestManager.Quests.Add(quest);
		return (quest, outer, outerAlternative, inner, firstLeaf, secondLeaf, successor);
	}

	private static void NestedBranchDebounceTracksEntirePath()
	{
		var x = NestedQuest(new[] { true, false, false, false }, new[] { true, true, true });
		x.quest.Update(); x.quest.Update(); x.quest.Update();
		Check(ReferenceEquals(x.quest.CurrentTask, x.outer), "inner-slot change reused the outer-slot debounce count");
		x.quest.Update();
		Check(ReferenceEquals(x.quest.CurrentTask, x.successor) && x.secondLeaf.Completed, "stable nested path did not complete after three checks");
	}

	private static void NestedLocalFrameCarriesCompletePath()
	{
		Terraria.Main.netMode = NetmodeID.MultiplayerClient; Terraria.Main.myPlayer = 6;
		var x = NestedQuest(new[] { false }, new[] { true });
		Check(x.outer.CheckCompletion(), "nested branch did not select a leaf");
		x.quest.Complete();
		using var reader = new BinaryReader(new MemoryStream(global::SpiritMod.SpiritMod.Instance.Packets.Single().ToArray()));
		reader.ReadByte(); reader.ReadBoolean(); reader.ReadString();
		Check(reader.ReadInt32() == x.outer.TaskID, "nested frame lost wrapper identity");
		Check(reader.ReadByte() == 2 && reader.ReadByte() == 1 && reader.ReadByte() == 1 && reader.ReadByte() == 6, "nested frame did not carry the complete selected path");
		Check(reader.BaseStream.Position == reader.BaseStream.Length, "nested local frame has trailing data");
	}

	private static void NestedLocalCompletionCommitsResolvedLeaf()
	{
		var x = NestedQuest(new[] { false }, new[] { true });
		Check(x.outer.CheckCompletion(), "nested branch did not select a leaf");
		x.quest.Complete();
		Check(x.outer.Completed && x.inner.Completed && x.secondLeaf.Completed, "nested wrappers and terminal leaf were not committed");
		Check(!x.outerAlternative.Completed && !x.firstLeaf.Completed && x.outerAlternative.DeactivateCalls == 0, "unselected outer branch was mutated");
		Check(x.firstLeaf.DeactivateCalls == 1 && x.secondLeaf.DeactivateCalls == 1, "selected nested subtree was not deactivated as one unit");
		Check(ReferenceEquals(x.quest.CurrentTask, x.successor) && x.successor.ActivateCalls == 1, "terminal leaf successor was not activated");
	}

	private static void NestedServerAppliesExactPath()
	{
		var x = NestedQuest();
		using var reader = ProgressPathReader(x.quest, new byte[] { 1, 1 }, 2);
		QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, true);
		Check(x.outer.Completed && x.inner.Completed && x.secondLeaf.Completed, "server did not commit the exact nested path");
		Check(!x.outerAlternative.Completed && !x.firstLeaf.Completed, "server mutated an unselected nested path");
		Check(ReferenceEquals(x.quest.CurrentTask, x.successor), "server chose the wrong nested successor");
	}

	private static void NestedServerRejectsIncompletePath()
	{
		var x = NestedQuest();
		using var reader = ProgressPathReader(x.quest, new byte[] { 1 }, 2);
		QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, true);
		Check(ReferenceEquals(x.quest.CurrentTask, x.outer) && !x.outer.Completed && !x.inner.Completed, "incomplete nested path mutated state");
		Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "incomplete nested path relayed");
	}

	private static void NestedServerRejectsOverlongPath()
	{
		var x = NestedQuest();
		using var reader = ProgressPathReader(x.quest, new byte[] { 1, 1, 0 }, 2);
		QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, true);
		Check(ReferenceEquals(x.quest.CurrentTask, x.outer) && !x.secondLeaf.Completed, "overlong nested path mutated state");
		Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "overlong nested path relayed");
	}

	private static void NestedServerRejectsSentinelSegment()
	{
		var x = NestedQuest();
		using var reader = ProgressPathReader(x.quest, new byte[] { 1, byte.MaxValue }, 2);
		QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, true);
		Check(ReferenceEquals(x.quest.CurrentTask, x.outer) && !x.inner.Completed, "sentinel path segment mutated state");
		Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "sentinel path segment relayed");
	}

	private static void NestedClientAppliesExactPathSilently()
	{
		var x = NestedQuest();
		using var reader = Reader(w => { w.Write(x.quest.QuestName); w.Write(x.outer.TaskID); w.Write((byte)2); w.Write((byte)1); w.Write((byte)0); });
		QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, false);
		Check(x.firstLeaf.Completed && !x.secondLeaf.Completed && ReferenceEquals(x.quest.CurrentTask, x.successor), "client did not apply the advertised nested path");
		Check(global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "client echoed a nested relay");
	}

	private static void NestedServerRelayPreservesCompletePath()
	{
		var x = NestedQuest();
		using var input = ProgressPathReader(x.quest, new byte[] { 1, 0 }, 5);
		QuestMultiplayer.HandlePacket(input, QuestMessageType.ProgressOrComplete, true);
		ModPacket packet = global::SpiritMod.SpiritMod.Instance.Packets.Single();
		Check(packet.Sent && packet.IgnoreClient == 5, "nested relay did not exclude the claimant");
		using var relay = new BinaryReader(new MemoryStream(packet.ToArray()));
		Check(relay.ReadByte() == (byte)QuestMessageType.ProgressOrComplete && !relay.ReadBoolean(), "nested relay header wrong");
		Check(relay.ReadString() == x.quest.QuestName && relay.ReadInt32() == x.outer.TaskID, "nested relay identity wrong");
		Check(relay.ReadByte() == 2 && relay.ReadByte() == 1 && relay.ReadByte() == 0 && relay.BaseStream.Position == relay.BaseStream.Length, "nested relay path was not canonical");
	}

	private static void ProgressRejectsTruncatedBranchPath()
	{
		var server = NestedQuest();
		using (var reader = Reader(w => { w.Write(server.quest.QuestName); w.Write(server.outer.TaskID); w.Write((byte)2); w.Write((byte)1); }))
			RejectMalformed(() => QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, true));
		Check(ReferenceEquals(server.quest.CurrentTask, server.outer) && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "truncated server path applied or relayed");
		var client = NestedQuest();
		using (var reader = Reader(w => { w.Write(client.quest.QuestName); w.Write(client.outer.TaskID); w.Write((byte)3); w.Write((byte)1); w.Write((byte)0); }))
			RejectMalformed(() => QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, false));
		Check(ReferenceEquals(client.quest.CurrentTask, client.outer), "truncated client path applied");
	}

	private static void CompletionDeactivateFailureRestoresTaskGraph()
	{
		var task = new ProbeTask(1) { Payload = new byte[] { 3 }, ThrowOnDeactivate = true };
		task.OnDeactivate = () => { task.Payload = new byte[] { 9 }; task.NextTask = null; };
		var successor = new ProbeTask(2); task.NextTask = successor;
		ProbeQuest quest = Quest(task, successor);
		RejectMalformed(() => quest.Complete());
		Check(ReferenceEquals(quest.CurrentTask, task) && !task.Completed && !quest.IsCompleted, "failed deactivation advanced completion state");
		Check(task.Payload.SequenceEqual(new byte[] { 3 }) && ReferenceEquals(task.NextTask, successor), "failed deactivation corrupted task payload or topology");
	}

	private static void CompletionSuccessorFailureRestoresTaskGraph()
	{
		var first = new ProbeTask(1) { Payload = new byte[] { 1 } };
		var second = new ProbeTask(2) { Payload = new byte[] { 2 } };
		second.OnActivate = () => { second.Payload = new byte[] { 8 }; second.Completed = true; throw new InvalidOperationException("activate after mutation"); };
		ProbeQuest quest = Quest(first, second);
		RejectMalformed(() => quest.Complete());
		Check(ReferenceEquals(quest.CurrentTask, first) && !first.Completed && !second.Completed, "failed successor activation advanced task state");
		Check(first.Payload.SequenceEqual(new byte[] { 1 }) && second.Payload.SequenceEqual(new byte[] { 2 }), "failed successor activation corrupted payloads");
	}

	private static void CompletionQuestHookFailureRestoresFlags()
	{
		var task = new ProbeTask(1) { Payload = new byte[] { 4 } };
		ProbeQuest quest = Quest(task);
		quest.OnQuestStateChanged += changed => { if (changed.IsCompleted) throw new InvalidOperationException("quest completion event"); };
		RejectMalformed(() => quest.Complete());
		Check(ReferenceEquals(quest.CurrentTask, task) && !task.Completed && !quest.IsCompleted, "throwing completion hook left committed flags");
		Check(task.Payload.SequenceEqual(new byte[] { 4 }), "throwing completion hook corrupted task payload");
	}

	private static void ServerProgressFailureRollsBackWithoutRelay()
	{
		var task = new ProbeTask(1) { Payload = new byte[] { 5 }, ThrowOnDeactivate = true };
		task.OnDeactivate = () => task.Payload = new byte[] { 6 };
		ProbeQuest quest = Quest(task);
		using var reader = ProgressReader(quest, byte.MaxValue, 2);
		RejectMalformed(() => QuestMultiplayer.HandlePacket(reader, QuestMessageType.ProgressOrComplete, true));
		Check(ReferenceEquals(quest.CurrentTask, task) && !task.Completed && task.Payload.SequenceEqual(new byte[] { 5 }), "failed server progress was not rolled back");
		Check(!QuestManager.Quiet && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "failed server progress leaked quiet or relay");
	}

	private static byte[] TaskFrame(int taskId, params byte[] payload)
	{
		using var stream = new MemoryStream();
		using (var writer = new BinaryWriter(stream, System.Text.Encoding.UTF8, true))
		{
			writer.Write(taskId); writer.Write((ushort)payload.Length); writer.Write(payload);
		}
		return stream.ToArray();
	}

	private static void TaskBufferDeactivateFailureRestoresGraph()
	{
		var current = new ProbeTask(1) { Payload = new byte[] { 1 }, ThrowOnDeactivate = true };
		var target = new ProbeTask(2) { Payload = new byte[] { 2 } };
		current.OnDeactivate = () => { current.Payload = new byte[] { 9 }; current.Completed = true; };
		var quest = new ProbeQuest(); quest.Configure(new QuestTask[] { current, target }, current);
		RejectMalformed(() => quest.ReadFromDataBuffer(TaskFrame(2, 7, 8)));
		Check(ReferenceEquals(quest.CurrentTask, current) && !current.Completed, "failed load deactivation changed selection or completion");
		Check(current.Payload.SequenceEqual(new byte[] { 1 }) && target.Payload.SequenceEqual(new byte[] { 2 }), "failed load deactivation did not restore all payloads");
	}

	private static void TaskBufferActivateFailureRestoresGraph()
	{
		var current = new ProbeTask(1) { Payload = new byte[] { 1 } };
		var target = new ProbeTask(2) { Payload = new byte[] { 2 } };
		current.OnDeactivate = () => current.Payload = new byte[] { 6 };
		target.OnActivate = () => { target.Payload = new byte[] { 9 }; target.Completed = true; throw new InvalidOperationException("target activation"); };
		var quest = new ProbeQuest(); quest.Configure(new QuestTask[] { current, target }, current);
		RejectMalformed(() => quest.ReadFromDataBuffer(TaskFrame(2, 7, 8)));
		Check(ReferenceEquals(quest.CurrentTask, current) && !target.Completed, "failed load activation changed selection or completion");
		Check(current.Payload.SequenceEqual(new byte[] { 1 }) && target.Payload.SequenceEqual(new byte[] { 2 }), "failed load activation did not restore all payloads");
	}

	private static void ServerActivatePostHookRollsBack()
	{
		var task = new ProbeTask(1) { Payload = new byte[] { 1 } }; ProbeQuest quest = Quest(task);
		QuestManager.AfterActivate = _ => { task.Payload = new byte[] { 9 }; throw new InvalidOperationException("post activate"); };
		using var reader = TransitionReader(quest.QuestName, 1);
		RejectMalformed(() => QuestMultiplayer.HandlePacket(reader, QuestMessageType.Activate, true));
		Check(!quest.IsActive && task.Payload.SequenceEqual(new byte[] { 1 }) && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "post-activate failure was committed or relayed");
	}

	private static void ServerDeactivatePostHookRollsBack()
	{
		var task = new ProbeTask(1) { Payload = new byte[] { 2 } }; ProbeQuest quest = Quest(task); quest.IsActive = true;
		QuestManager.AfterDeactivate = _ => { task.Payload = new byte[] { 8 }; throw new InvalidOperationException("post deactivate"); };
		using var reader = TransitionReader(quest.QuestName, 1);
		RejectMalformed(() => QuestMultiplayer.HandlePacket(reader, QuestMessageType.Deactivate, true));
		Check(quest.IsActive && task.Payload.SequenceEqual(new byte[] { 2 }) && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "post-deactivate failure was committed or relayed");
	}

	private static void ServerUnlockPostHookRollsBack()
	{
		ProbeQuest quest = Quest(new ProbeTask(1)); quest.UnlockTime = 17;
		QuestManager.AfterUnlock = _ => { quest.UnlockTime = 99; throw new InvalidOperationException("post unlock"); };
		using var reader = TransitionReader(quest.QuestName, 1);
		RejectMalformed(() => QuestMultiplayer.HandlePacket(reader, QuestMessageType.Unlock, true));
		Check(!quest.IsUnlocked && quest.UnlockTime == 17 && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "post-unlock failure was committed or relayed");
	}

	private static void BookPostHookRollsBack()
	{
		QuestManager.AfterUnlockQuestBook = () => throw new InvalidOperationException("post book unlock");
		using var reader = Reader(w => w.Write((byte)1));
		RejectMalformed(() => QuestMultiplayer.HandlePacket(reader, QuestMessageType.ObtainQuestBook, true));
		Check(!QuestManager.QuestBookUnlocked && global::SpiritMod.SpiritMod.Instance.Packets.Count == 0, "post-book failure was committed or relayed");
	}

    private static void RejectMalformed(Action action)
    {
        try { action(); }
        catch (Exception) { }
    }

    private static void Expect<T>(Action action) where T : Exception
    {
        try { action(); }
        catch (T) { return; }
        throw new InvalidOperationException($"expected {typeof(T).Name}");
    }
}

internal sealed class ProbeQuest : Quest
{
    public void Configure(IEnumerable<QuestTask> tasks, QuestTask current)
    {
        _tasks = new TaskBuilder(tasks.ToArray());
        _currentTask = current;
    }
    public void Complete(int slot = byte.MaxValue) => RunCompletion(slot);
}

internal sealed class ProbeTask : QuestTask
{
    private readonly Queue<bool> _checks;
    private bool _last;
    public int CheckCalls { get; private set; }
    public int ActivateCalls { get; private set; }
    public int DeactivateCalls { get; private set; }
    public int ResetCalls { get; private set; }
    public int ReadLength { get; set; } = -1;
    public byte[] Payload { get; set; } = Array.Empty<byte>();
    public bool ThrowOnDeactivate { get; set; }
    public int ThrowsAfterRead { get; set; }
	public Action OnActivate { get; set; }
    public Action OnDeactivate { get; set; }

    public ProbeTask(int id, params bool[] checks)
    {
        TaskID = id;
        _checks = new Queue<bool>(checks);
        if (checks.Length > 0) _last = checks[^1];
    }
    public void SetChecks(params bool[] checks)
    {
        _checks.Clear();
        foreach (bool value in checks) _checks.Enqueue(value);
        if (checks.Length > 0) _last = checks[^1];
    }
    public override bool CheckCompletion()
    {
        CheckCalls++;
        if (_checks.Count > 0) _last = _checks.Dequeue();
        return _last;
    }
	public override void Activate(Quest fromQuest)
	{
		ActivateCalls++;
		OnActivate?.Invoke();
	}
    public override void Deactivate()
    {
        DeactivateCalls++;
        OnDeactivate?.Invoke();
        if (ThrowOnDeactivate) throw new InvalidOperationException("task deactivate failed");
    }
    public override void ResetProgress() { base.ResetProgress(); ResetCalls++; }
    public override void WriteData(BinaryWriter writer) => writer.Write(Payload);
    public override void ReadData(BinaryReader reader)
    {
        int count = ReadLength < 0 ? (int)(reader.BaseStream.Length - reader.BaseStream.Position) : ReadLength;
        byte[] bytes = reader.ReadBytes(count);
        if (bytes.Length != count) throw new EndOfStreamException();
        Payload = bytes;
        if (ThrowsAfterRead > 0)
        {
            ThrowsAfterRead--;
            throw new InvalidDataException("task read failed after mutation");
        }
    }
}
