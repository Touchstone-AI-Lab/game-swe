using System;
using System.IO;
using System.Linq;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;
using SpiritMod.Mechanics.QuestSystem.Tasks;

namespace SpiritMod.Mechanics.QuestSystem
{
	class QuestMultiplayer
	{
		internal static void HandlePacket(BinaryReader reader, QuestMessageType messageType, bool forServer)
		{
			if (forServer)
				HandleServerPacket(reader, messageType);
			else
				HandleClientPacket(reader, messageType);
		}

		private static void HandleServerPacket(BinaryReader reader, QuestMessageType messageType)
		{
			if (messageType == QuestMessageType.Deactivate || messageType == QuestMessageType.Activate || messageType == QuestMessageType.Unlock)
			{
				string name = reader.ReadString();
				byte playerId = reader.ReadByte();
				if (!AtEnd(reader) || playerId >= Main.maxPlayers || !CanApplyQuestTransition(name, messageType))
					return;

				if (messageType == QuestMessageType.Deactivate)
					DeactivateQuest(name);
				else if (messageType == QuestMessageType.Activate)
					ActivateQuest(name);
				else
					UnlockQuest(name);

				ModPacket packet = SpiritMod.Instance.GetPacket(MessageType.Quest, 4);
				packet.Write((byte)messageType);
				packet.Write(false);
				packet.Write(name);
				packet.Send(-1, playerId);
				return;
			}

			if (messageType == QuestMessageType.ProgressOrComplete)
			{
				string name = reader.ReadString();
				int expectedTaskId = reader.ReadInt32();
				byte[] taskPath = ReadTaskPath(reader);
				byte playerId = reader.ReadByte();
				if (!AtEnd(reader) || playerId >= Main.maxPlayers || !CanCompleteQuestOrTask(name, expectedTaskId, taskPath))
					return;

				CompleteQuestOrTask(name, expectedTaskId, taskPath);
				ModPacket packet = SpiritMod.Instance.GetPacket(MessageType.Quest, 10 + taskPath.Length);
				packet.Write((byte)QuestMessageType.ProgressOrComplete);
				packet.Write(false);
				packet.Write(name);
				packet.Write(expectedTaskId);
				packet.Write((byte)taskPath.Length);
				foreach (byte slot in taskPath)
					packet.Write(slot);
				packet.Send(-1, playerId);
				return;
			}

			if (messageType == QuestMessageType.ObtainQuestBook)
			{
				byte playerId = reader.ReadByte();
				if (!AtEnd(reader) || playerId >= Main.maxPlayers || QuestManager.QuestBookUnlocked)
					return;

				UnlockQuestBook();
				ModPacket packet = SpiritMod.Instance.GetPacket(MessageType.Quest, 3);
				packet.Write((byte)QuestMessageType.ObtainQuestBook);
				packet.Write(false);
				packet.Send(-1, playerId);
				return;
			}

			if (messageType == QuestMessageType.SyncNPCQueue)
			{
				ushort npcID = reader.ReadUInt16();
				byte playerId = reader.ReadByte();
				if (!AtEnd(reader) || playerId >= Main.maxPlayers || !TryRemoveFromNPCQueue(npcID))
					return;

				ModPacket packet = SpiritMod.Instance.GetPacket(MessageType.Quest, 4);
				packet.Write((byte)QuestMessageType.SyncNPCQueue);
				packet.Write(false);
				packet.Write(npcID);
				packet.Send(-1, playerId);
			}
		}

		private static void HandleClientPacket(BinaryReader reader, QuestMessageType messageType)
		{
			if (messageType == QuestMessageType.Deactivate || messageType == QuestMessageType.Activate || messageType == QuestMessageType.Unlock)
			{
				string name = reader.ReadString();
				if (!AtEnd(reader) || !CanApplyQuestTransition(name, messageType))
					return;
				if (messageType == QuestMessageType.Deactivate)
					DeactivateQuest(name);
				else if (messageType == QuestMessageType.Activate)
					ActivateQuest(name);
				else
					UnlockQuest(name);
				return;
			}

			if (messageType == QuestMessageType.ProgressOrComplete)
			{
				string name = reader.ReadString();
				int expectedTaskId = reader.ReadInt32();
				byte[] taskPath = ReadTaskPath(reader);
				if (AtEnd(reader) && CanCompleteQuestOrTask(name, expectedTaskId, taskPath))
					CompleteQuestOrTask(name, expectedTaskId, taskPath);
				return;
			}

			if (messageType == QuestMessageType.SyncOnNPCLoot)
			{
				int npcIndex = reader.ReadByte();
				if (AtEnd(reader) && npcIndex >= 0 && npcIndex < Main.npc.Length)
					ModContent.GetInstance<QuestGlobalNPC>().ClientNPCLoot(Main.npc[npcIndex]);
				return;
			}

			if (messageType == QuestMessageType.ObtainQuestBook)
			{
				if (AtEnd(reader) && !QuestManager.QuestBookUnlocked)
					UnlockQuestBook();
				return;
			}

			if (messageType == QuestMessageType.SyncNPCQueue)
			{
				ushort npcID = reader.ReadUInt16();
				if (AtEnd(reader))
					RemoveFromNPCQueue(npcID);
			}
		}

		/// <summary>Writes name, a long bitflag value containing StoredQuestData, and the Buffer if it has one.</summary>
		public static void WriteQuestToPacket(ModPacket packet, Quest quest)
		{
			if (packet == null || quest == null)
				throw new ArgumentNullException(packet == null ? nameof(packet) : nameof(quest));

			StoredQuestData data = QuestWorld.ToStoredQuest(quest) ?? throw new InvalidDataException("Quest snapshot data is missing.");
			byte[] buffer = data.Buffer == null ? null : (byte[])data.Buffer.Clone();
			if (buffer != null && buffer.Length > byte.MaxValue)
				throw new InvalidDataException("Quest task buffers cannot exceed 255 bytes.");

			long flags = (long)(ushort)data.TimeLeftActive << 48;
			flags |= (long)(ushort)data.TimeLeftUnlocked << 32;
			flags |= (long)data.RewardsGiven.ToInt() << 16;
			flags |= (long)data.IsCompleted.ToInt() << 15;
			flags |= (long)data.IsActive.ToInt() << 14;
			flags |= (long)data.IsUnlocked.ToInt() << 13;

			packet.Write(quest.QuestName);
			packet.Write(flags);
			packet.Write((byte)(buffer?.Length ?? 0));
			if (buffer != null)
				foreach (byte value in buffer)
					packet.Write(value);
		}

		public static StoredQuestData ReadQuestFromLong(long flags)
		{
			return new StoredQuestData
			{
				IsUnlocked = (flags & (1L << 13)) != 0,
				IsActive = (flags & (1L << 14)) != 0,
				IsCompleted = (flags & (1L << 15)) != 0,
				RewardsGiven = (flags & (1L << 16)) != 0,
				TimeLeftActive = unchecked((short)((ulong)flags >> 48)),
				TimeLeftUnlocked = unchecked((short)(((ulong)flags >> 32) & ushort.MaxValue))
			};
		}

		internal static void DeactivateQuest(string questName)
		{
			Quest quest = FindQuest(questName);
			if (quest == null)
				return;
			WithQuiet(() => quest.RunStateTransaction(() => QuestManager.DeactivateQuest(quest)));
		}

		internal static void ActivateQuest(string questName)
		{
			Quest quest = FindQuest(questName);
			if (quest == null)
				return;
			WithQuiet(() => quest.RunStateTransaction(() => QuestManager.ActivateQuest(quest)));
		}

		internal static void CompleteQuestOrTask(string questName, byte taskSlot)
		{
			Quest quest = FindQuest(questName);
			if (quest == null)
				return;
			WithQuiet(() => quest.RunCompletion(taskSlot));
		}

		internal static void CompleteQuestOrTask(string questName, int expectedTaskId, byte taskSlot)
		{
			Quest quest = FindQuest(questName);
			if (quest == null)
				return;
			WithQuiet(() => quest.RunCompletion(expectedTaskId, taskSlot));
		}

		internal static void CompleteQuestOrTask(string questName, int expectedTaskId, byte[] taskPath)
		{
			Quest quest = FindQuest(questName);
			if (quest == null)
				return;
			WithQuiet(() => quest.RunCompletion(expectedTaskId, taskPath));
		}

		private static bool CanCompleteQuestOrTask(string questName, int expectedTaskId, byte taskSlot)
			=> CanCompleteQuestOrTask(questName, expectedTaskId, taskSlot == byte.MaxValue ? Array.Empty<byte>() : new[] { taskSlot });

		private static bool CanCompleteQuestOrTask(string questName, int expectedTaskId, byte[] taskPath)
		{
			Quest quest = FindQuest(questName);
			if (quest == null || quest.IsCompleted || quest.CurrentTask == null || quest.CurrentTask.TaskID != expectedTaskId)
				return false;

			if (quest.CurrentTask is BranchingTask branch)
				return branch.TryResolvePath(taskPath, out _, out _, out _);
			return taskPath != null && taskPath.Length == 0;
		}

		private static bool CanApplyQuestTransition(string questName, QuestMessageType messageType)
		{
			Quest quest = FindQuest(questName);
			if (quest == null)
				return false;
			if (messageType == QuestMessageType.Deactivate)
				return quest.IsActive;
			if (messageType == QuestMessageType.Activate)
				return !quest.IsActive;
			return messageType == QuestMessageType.Unlock && !quest.IsUnlocked;
		}

		internal static void UnlockQuest(string questName)
		{
			Quest quest = FindQuest(questName);
			if (quest == null || quest.IsUnlocked)
				return;
			WithQuiet(() => quest.RunStateTransaction(() => QuestManager.UnlockQuest(quest, Main.netMode != NetmodeID.Server)));
		}

		internal static void RemoveFromNPCQueue(ushort npcID) => TryRemoveFromNPCQueue(npcID);

		private static bool TryRemoveFromNPCQueue(ushort npcID)
		{
			if (!ModContent.GetInstance<QuestWorld>().NPCQuestQueue.TryGetValue(npcID, out var queue) || queue.Count == 0)
				return false;
			queue.Dequeue();
			return true;
		}

		private static Quest FindQuest(string questName)
			=> QuestManager.Quests.FirstOrDefault(x => x.QuestName == questName);

		private static bool AtEnd(BinaryReader reader)
			=> reader.BaseStream.Position == reader.BaseStream.Length;

		private static byte[] ReadTaskPath(BinaryReader reader)
		{
			int length = reader.ReadByte();
			byte[] path = reader.ReadBytes(length);
			if (path.Length != length)
				throw new EndOfStreamException("Quest progress branch path is truncated.");
			return path;
		}

		private static void UnlockQuestBook()
		{
			bool previous = QuestManager.QuestBookUnlocked;
			try
			{
				QuestManager.UnlockQuestBook(false);
			}
			catch
			{
				QuestManager.QuestBookUnlocked = previous;
				throw;
			}
		}

		private static void WithQuiet(Action action)
		{
			bool previousQuiet = QuestManager.Quiet;
			QuestManager.Quiet = true;
			try { action(); }
			finally { QuestManager.Quiet = previousQuiet; }
		}
	}
}
