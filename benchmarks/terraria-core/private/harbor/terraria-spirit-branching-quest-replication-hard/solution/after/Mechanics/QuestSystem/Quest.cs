using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using System;
using System.Collections.Generic;
using System.Text;
using System.IO;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;
using SpiritMod.Mechanics.QuestSystem.Tasks;
using SpiritMod.UI.Elements;
using Terraria.Localization;
using SpiritMod.NPCs.Town;
using System.Linq;
using Terraria.Chat;
using SpiritMod.Utilities;

namespace SpiritMod.Mechanics.QuestSystem
{
	public abstract class Quest
	{
		protected TaskBuilder _tasks;
		protected QuestTask _currentTask;
		private bool _questActive;
		private bool _questUnlocked;
		private bool _questCompleted;
		private bool _rewardsGiven;
		private int _completedCounter = 0;
		private byte[] _completedTaskPath = Array.Empty<byte>();
		private bool _previouslyUnavailable = false;

		internal List<string> _altNames;

		public QuestTask CurrentTask => _currentTask;

		/// <summary>
		/// Used for localization (i.e. <see cref="FullLangKey"/>) and saving/loading, as <see cref="QuestName"/> is a localized value.
		/// </summary>
		public virtual string QuestKey => GetType().Name;

		/// <summary>
		/// Full path: <code>"Mods.SpiritMod.Quests.QuestInfo." + <see cref="QuestKey"/>;</code>
		/// </summary>
		public string FullLangKey => "Mods.SpiritMod.Quests.QuestInfo." + QuestKey;

		/// <summary>
		/// Quest-only path, mainly for use in <see cref="QuestManager.Localization(string)"/> or <see cref="QuestManager.LocalizationValue(string)"/>.<br/>
		/// Path: <code>"QuestInfo." + <see cref="QuestKey"/>;</code>
		/// </summary>
		public string ShortLangKey => "QuestInfo." + QuestKey;

		public string QuestName => Language.GetTextValue(FullLangKey + ".Name");
		public string QuestDescription => Language.GetTextValue(FullLangKey + ".Description");

		public virtual int QuestClientID => ModContent.NPCType<Adventurer>();
		public virtual string QuestClientOverride => null;
		public string QuestClient => QuestClientOverride ?? QuestManager.LocalizationValue("The") + Lang.GetNPCNameValue(QuestClientID);

		public virtual string QuestCategory => "";

		public virtual int Difficulty => 1;
		public virtual (int, int)[] QuestRewards => null;
		public virtual bool TutorialActivateButton => false;
		public virtual Texture2D QuestImage { get; set; }

		public virtual bool AppearsWhenUnlocked => true;
		public virtual bool CountsTowardsQuestTotal => true;
		public virtual bool AnnounceRelocking => false;
		public virtual bool LimitedUnlock => false;
		public virtual bool AnnounceDeactivation => false;
		public virtual bool LimitedActive => false;
		public int UnlockTime { get; set; }
		public int ActiveTime { get; set; }

		public int QuestCategoryIndex => QuestManager.GetCategoryInfo(QuestCategory).Index;

		public bool IsActive
		{
			get => _questActive; set
			{
				_questActive = value;
				OnQuestStateChanged?.Invoke(this);

				if (value)
					OnActivate();
				else
					OnDeactivate();
			}
		}

		public virtual bool IsUnlocked { get => _questUnlocked; set { _questUnlocked = value; OnQuestStateChanged?.Invoke(this); } }
		public bool IsCompleted { get => _questCompleted; set { _questCompleted = value; OnQuestStateChanged?.Invoke(this); } }
		public bool RewardsGiven { get => _rewardsGiven; set { _rewardsGiven = value; OnQuestStateChanged?.Invoke(this); } }
		public int WhoAmI { get; set; }

		public event Action<Quest> OnQuestStateChanged;

		public Quest()
		{
			_altNames = new List<string>();
			_tasks = new TaskBuilder();
		}

		public LocalizedText GetText(string key) => QuestManager.Localization(ShortLangKey + "." + key);

		public virtual string GetObjectivesBook()
		{
			var lines = new List<string>();
			var final = new List<(string, bool)>();

			for (QuestTask task = _tasks.Start; task != null; task = task.NextTask)
			{
				task.GetBookText(lines);
				foreach (string s in lines)
				{
					final.Add((s, task.Completed));
				}
				lines.Clear();
			}

			StringBuilder builder = new StringBuilder();
			for (int i = 0; i < final.Count; i++)
			{
				builder.Append("- ").Append(final[i].Item1);

				if (i < final.Count - 1) 
					builder.Append('\n');
			}

			return builder.ToString();
		}

		public virtual string GetObjectivesHUD()
		{
			var lines = new List<string>();
			_currentTask.GetHUDText(lines);

			StringBuilder builder = new StringBuilder();
			for (int i = 0; i < lines.Count; i++)
			{
				builder.Append("- ").Append(lines[i]);

				if (i < lines.Count - 1) builder.Append('\n');
			}

			return builder.ToString();
		}

		public virtual void OnQuestComplete()
		{
			IsCompleted = true;
			QuestManager.SayInChat(QuestManager.Localization("QuestCompleteChat").WithFormatArgs(WhoAmI, QuestName), Color.White, true);
		}

		public virtual void OnUnlock() { }

		public virtual void OnActivate()
		{
			_currentTask = _tasks.Start;

			_currentTask.Activate(this);
		}

		public virtual void OnDeactivate() => _currentTask?.Deactivate();

		public virtual void ResetEverything()
		{
			ResetAllProgress();
			IsActive = false;
			IsCompleted = false;
			IsUnlocked = false;
			RewardsGiven = false;
		}

		public virtual void ResetAllProgress()
		{
			for (QuestTask task = _tasks.Start; task != null; task = task.NextTask)
				task.ResetProgress();
		}

		public virtual void UpdateBookOverlay(UIShaderImage image) => image.Texture = null;

		public virtual void Update()
		{
			if (LimitedActive)
			{
				ActiveTime--;
				if (ActiveTime <= 0)
				{
					if (AnnounceDeactivation)
						QuestManager.SayInChat(QuestManager.Localization("QuestOutOfTimeChat").WithFormatArgs(WhoAmI, QuestName), Color.White);

					QuestManager.DeactivateQuest(this);
				}
			}

			if (_currentTask.CheckCompletion())
			{
				byte[] taskPath = Array.Empty<byte>();
				if (_currentTask is BranchingTask branch && !branch.TryGetSelectedPath(out taskPath))
				{
					ResetCompletionDebounce();
					return;
				}
				taskPath ??= Array.Empty<byte>();
				if (_completedCounter == 0 || _completedTaskPath.SequenceEqual(taskPath))
					_completedCounter++;
				else
					_completedCounter = 1;
				_completedTaskPath = (byte[])taskPath.Clone();

				if (_completedCounter >= 3)
					RunCompletionCore(null, taskPath);
			}
			else
				ResetCompletionDebounce();

			if (IsQuestPossible() && _previouslyUnavailable)
			{
				_previouslyUnavailable = false;
				QuestManager.SayInChat(QuestManager.Localization("NewQuestChat").WithFormatArgs(WhoAmI, QuestName), Color.White);
			}
		}

		internal void RunCompletion(int taskArgument = byte.MaxValue)
		{
			if (taskArgument < byte.MinValue || taskArgument > byte.MaxValue)
				return;
			byte value = (byte)taskArgument;
			RunCompletionCore(null, value == byte.MaxValue ? Array.Empty<byte>() : new[] { value });
		}

		internal void RunCompletion(int expectedTaskId, byte taskArgument)
			=> RunCompletionCore(expectedTaskId, taskArgument == byte.MaxValue ? Array.Empty<byte>() : new[] { taskArgument });

		internal void RunCompletion(int expectedTaskId, byte[] taskPath)
			=> RunCompletionCore(expectedTaskId, taskPath);

		private void RunCompletionCore(int? expectedTaskId, IReadOnlyList<byte> advertisedPath)
		{
			if (IsCompleted)
				return;
			if (expectedTaskId.HasValue && (_currentTask == null || _currentTask.TaskID != expectedTaskId.Value))
				return;

			QuestTask selectedChild = _currentTask;
			QuestTask terminal = _currentTask;
			BranchingTask branchTask = _currentTask as BranchingTask;
			BranchingTask[] wrappers = Array.Empty<BranchingTask>();
			byte[] taskPath = advertisedPath?.ToArray() ?? Array.Empty<byte>();
			if (branchTask != null)
			{
				if (!QuestManager.Quiet && !branchTask.TryGetSelectedPath(out taskPath))
					return;
				if (!branchTask.TryResolvePath(taskPath, out selectedChild, out terminal, out wrappers))
					return;
			}
			else if (taskPath.Length != 0)
				return;

			QuestStateSnapshot snapshot = QuestStateSnapshot.Capture(this);
			try
			{
				if (terminal is not null) //This should only be true when the quest is force-completed
				{
					if (!QuestManager.Quiet && Main.netMode == NetmodeID.MultiplayerClient) //Tell server to progress the quest.
					{
						ModPacket packet = SpiritMod.Instance.GetPacket(MessageType.Quest, 10 + taskPath.Length);
						packet.Write((byte)QuestMessageType.ProgressOrComplete);
						packet.Write(true);
						packet.Write(QuestName);
						packet.Write(_currentTask.TaskID);
						packet.Write((byte)taskPath.Length);
						foreach (byte slot in taskPath)
							packet.Write(slot);
						packet.Write((byte)Main.myPlayer);
						packet.Send();
					}

					QuestTask successor = terminal.NextTask;
					foreach (BranchingTask wrapper in wrappers)
						wrapper.Completed = true;
					if (branchTask != null)
						branchTask.CommitPath(taskPath, successor);
					terminal.Completed = true;
					selectedChild.Completed = true;
					selectedChild.Deactivate();
					_currentTask = successor;
					ResetCompletionDebounce();
				}

				if (_currentTask is null) //Quest completed
				{
					OnQuestComplete();
					QuestManager.DeactivateQuest(this);
				}
				else //Quest continues
					_currentTask.Activate(this);
			}
			catch
			{
				snapshot.Restore(this);
				throw;
			}
		}

		private void ResetCompletionDebounce()
		{
			_completedCounter = 0;
			_completedTaskPath = Array.Empty<byte>();
		}

		public virtual bool IsQuestPossible() => true;

		public virtual void OnMPSync()
		{
			for (QuestTask task = _tasks.Start; task != null; task = task.NextTask)
				task.OnMPSyncTick();
		}

		public virtual byte[] GetTaskDataBuffer()
		{
			if (_currentTask == null)
				throw new InvalidOperationException("A completed quest has no current task data.");
			byte[] payload = SerializeTask(_currentTask);
			if (payload.Length > ushort.MaxValue)
				throw new InvalidDataException("Quest task data exceeds 65535 bytes.");

			using var stream = new MemoryStream();
			using var writer = new BinaryWriter(stream);
			writer.Write(_currentTask.TaskID);
			writer.Write((ushort)payload.Length);
			writer.Write(payload);
			writer.Flush();
			return stream.ToArray();
		}

		public virtual void ReadFromDataBuffer(byte[] buffer)
		{
			if (buffer == null || buffer.Length < sizeof(int) + sizeof(ushort))
				throw new InvalidDataException("Quest task data is missing its framed header.");

			using var stream = new MemoryStream(buffer);
			using var reader = new BinaryReader(stream);
			int taskId = reader.ReadInt32();
			int payloadLength = reader.ReadUInt16();
			if (payloadLength != stream.Length - stream.Position)
				throw new InvalidDataException("Quest task payload length does not match its frame.");
			byte[] payload = reader.ReadBytes(payloadLength);
			QuestTask task;
			try
			{
				task = _tasks[taskId];
			}
			catch (Exception error) when (error is ArgumentException || error is IndexOutOfRangeException || error is KeyNotFoundException)
			{
				throw new InvalidDataException($"Unknown quest task identifier {taskId}.", error);
			}
			if (task == null)
				throw new InvalidDataException($"Unknown quest task identifier {taskId}.");

			QuestStateSnapshot snapshot = QuestStateSnapshot.Capture(this);
			try
			{
				ReadTaskExactly(task, payload);
				if (ReferenceEquals(_currentTask, task))
					return;

				_currentTask?.Deactivate();
				_currentTask = task;
				task.Activate(this); //Fixes branch quests being poorly reloaded
			}
			catch
			{
				snapshot.Restore(this);
				throw;
			}
		}

		internal void RunStateTransaction(Action action)
		{
			if (action == null)
				throw new ArgumentNullException(nameof(action));
			QuestStateSnapshot snapshot = QuestStateSnapshot.Capture(this);
			try
			{
				action();
			}
			catch
			{
				snapshot.Restore(this);
				throw;
			}
		}

		private static byte[] SerializeTask(QuestTask task)
		{
			using var stream = new MemoryStream();
			using (var writer = new BinaryWriter(stream, Encoding.UTF8, true))
				task.WriteData(writer);
			return stream.ToArray();
		}

		private static void ReadTaskExactly(QuestTask task, byte[] payload)
		{
			using var stream = new MemoryStream(payload, writable: false);
			using var reader = new BinaryReader(stream);
			task.ReadData(reader);
			if (stream.Position != stream.Length)
				throw new InvalidDataException("Quest task did not consume its complete payload.");
		}

		private sealed class QuestStateSnapshot
		{
			private readonly QuestTask _currentTask;
			private readonly bool _questActive;
			private readonly bool _questUnlocked;
			private readonly bool _questCompleted;
			private readonly bool _rewardsGiven;
			private readonly int _completedCounter;
			private readonly byte[] _completedTaskPath;
			private readonly bool _previouslyUnavailable;
			private readonly int _unlockTime;
			private readonly int _activeTime;
			private readonly TaskState[] _tasks;

			private QuestStateSnapshot(Quest quest, TaskState[] tasks)
			{
				_currentTask = quest._currentTask;
				_questActive = quest._questActive;
				_questUnlocked = quest._questUnlocked;
				_questCompleted = quest._questCompleted;
				_rewardsGiven = quest._rewardsGiven;
				_completedCounter = quest._completedCounter;
				_completedTaskPath = (byte[])quest._completedTaskPath.Clone();
				_previouslyUnavailable = quest._previouslyUnavailable;
				_unlockTime = quest.UnlockTime;
				_activeTime = quest.ActiveTime;
				_tasks = tasks;
			}

			internal static QuestStateSnapshot Capture(Quest quest)
			{
				var registered = new List<QuestTask>();
				if (quest._tasks?.AllTasks != null)
					registered.AddRange(quest._tasks.AllTasks.Where(task => task != null));
				if (quest._currentTask != null && !registered.Contains(quest._currentTask))
					registered.Add(quest._currentTask);

				TaskState[] states = registered.Distinct().Select(task => new TaskState(task)).ToArray();
				return new QuestStateSnapshot(quest, states);
			}

			internal void Restore(Quest quest)
			{
				foreach (TaskState state in _tasks)
					ReadTaskExactly(state.Task, state.Payload);
				foreach (TaskState state in _tasks)
				{
					state.Task.Completed = state.Completed;
					state.Task.NextTask = state.NextTask;
				}

				quest._currentTask = _currentTask;
				quest._questActive = _questActive;
				quest._questUnlocked = _questUnlocked;
				quest._questCompleted = _questCompleted;
				quest._rewardsGiven = _rewardsGiven;
				quest._completedCounter = _completedCounter;
				quest._completedTaskPath = (byte[])_completedTaskPath.Clone();
				quest._previouslyUnavailable = _previouslyUnavailable;
				quest.UnlockTime = _unlockTime;
				quest.ActiveTime = _activeTime;
			}

			private sealed class TaskState
			{
				internal QuestTask Task { get; }
				internal bool Completed { get; }
				internal QuestTask NextTask { get; }
				internal byte[] Payload { get; }

				internal TaskState(QuestTask task)
				{
					Task = task;
					Completed = task.Completed;
					NextTask = task.NextTask;
					Payload = SerializeTask(task);
				}
			}
		}

		public void GiveRewards()
		{
			if (Main.netMode == NetmodeID.Server)
				return;

			foreach (var itemPair in QuestRewards)
				ItemUtils.NewItemWithSync(Main.LocalPlayer.GetSource_GiftOrReward(), Main.myPlayer, Main.LocalPlayer.getRect(), ContentDefinition.GetItemDefinition(itemPair.Item1), itemPair.Item2);
		}

		public static void ModifySpawnRateUnique(IDictionary<int, float> pool, int id, float rate)
		{
			if (pool.TryGetValue(id, out float value) && value > 0f && !NPC.AnyNPCs(id))
				pool[id] = rate;
		}

		// TODO: Write Packet and ReadPacket
		// TODO: Have each quest section have it's own WritePacket and ReadPacket
	}
}
