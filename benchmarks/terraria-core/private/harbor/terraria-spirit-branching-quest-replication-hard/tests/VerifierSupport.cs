using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace Microsoft.Xna.Framework
{
    public struct Color { public static Color White => new(); }
}

namespace Microsoft.Xna.Framework.Graphics
{
    public class Texture2D { }
}

namespace Terraria
{
    public static class BoolExtensions { public static int ToInt(this bool value) => value ? 1 : 0; }
    public class NPC { public static bool AnyNPCs(int id) => false; }
    public class Player
    {
        public object GetSource_GiftOrReward() => new();
        public object getRect() => new();
    }

    public static class Main
    {
        public static int netMode;
        public static int myPlayer;
        public static int maxPlayers = 8;
        public static Player LocalPlayer = new();
        public static NPC[] npc = Enumerable.Range(0, 256).Select(_ => new NPC()).ToArray();
    }

    public static class Lang
    {
        public static string GetNPCNameValue(int id) => $"NPC-{id}";
    }

}

namespace Terraria.ID
{
    public static class NetmodeID
    {
        public const int SinglePlayer = 0;
        public const int MultiplayerClient = 1;
        public const int Server = 2;
    }
}

namespace Terraria.Localization
{
    public sealed class LocalizedText
    {
        public string Value { get; }
        public LocalizedText(string value) => Value = value;
        public LocalizedText WithFormatArgs(params object[] args) => new(string.Format(Value, args));
        public override string ToString() => Value;
    }

    public static class Language
    {
        public static string GetTextValue(string key) => key;
    }

    public sealed class NetworkText { }
}

namespace Terraria.Chat
{
    public static class ChatHelper { }
}

namespace Terraria.ModLoader
{
    public class ModPacket
    {
        private readonly MemoryStream _stream = new();
        private readonly BinaryWriter _writer;
        public int ToClient { get; private set; } = int.MinValue;
        public int IgnoreClient { get; private set; } = int.MinValue;
        public bool Sent { get; private set; }

        public ModPacket() => _writer = new BinaryWriter(_stream);
        public void Write(byte value) => _writer.Write(value);
        public void Write(bool value) => _writer.Write(value);
        public void Write(string value) => _writer.Write(value);
        public void Write(int value) => _writer.Write(value);
        public void Write(long value) => _writer.Write(value);
        public void Write(ushort value) => _writer.Write(value);
        public byte[] ToArray() { _writer.Flush(); return _stream.ToArray(); }
        public void Send(int toClient = -1, int ignoreClient = -1)
        {
            Sent = true;
            ToClient = toClient;
            IgnoreClient = ignoreClient;
        }
    }

    public static class ModContent
    {
        private static readonly Dictionary<Type, object> Instances = new();
        public static int NPCType<T>() => typeof(T).FullName.GetHashCode();
        public static T GetInstance<T>() where T : new()
        {
            if (!Instances.TryGetValue(typeof(T), out object value))
                Instances[typeof(T)] = value = new T();
            return (T)value;
        }
        public static void ClearInstances() => Instances.Clear();
    }
}

namespace SpiritMod
{
    public enum MessageType : byte { Quest = 17 }
    public enum QuestMessageType : byte
    {
        Deactivate,
        Activate,
        ProgressOrComplete,
        ObtainQuestBook,
        Unlock,
        SyncNPCQueue,
        SyncOnNPCLoot,
    }

    public sealed class SpiritMod
    {
        public static SpiritMod Instance { get; } = new();
        public List<Terraria.ModLoader.ModPacket> Packets { get; } = new();
        public Terraria.ModLoader.ModPacket GetPacket(MessageType _, int __)
        {
            var packet = new Terraria.ModLoader.ModPacket();
            Packets.Add(packet);
            return packet;
        }
        public void Reset() => Packets.Clear();
    }
}

namespace SpiritMod.UI.Elements
{
    public sealed class UIShaderImage { public Microsoft.Xna.Framework.Graphics.Texture2D Texture { get; set; } }
}

namespace SpiritMod.NPCs.Town
{
    public sealed class Adventurer { }
}

namespace SpiritMod.Utilities
{
    public static class ContentDefinition
    {
        public static object GetItemDefinition(int id) => id;
    }

    public static class ItemUtils
    {
        public static void NewItemWithSync(object source, int player, object rect, object definition, int stack) { }
    }
}

namespace SpiritMod.Mechanics.QuestSystem
{
    using global::SpiritMod.Mechanics.QuestSystem.Tasks;

    public sealed class TaskBuilder
    {
        private readonly Dictionary<int, QuestTask> _tasks = new();
        public QuestTask Start { get; private set; }
		public List<QuestTask> AllTasks { get; } = new();
        public TaskBuilder() { }
        public TaskBuilder(params QuestTask[] tasks) => Set(tasks);
        public QuestTask this[int id] => _tasks.TryGetValue(id, out QuestTask task) ? task : null;
        public void Set(params QuestTask[] tasks)
        {
            _tasks.Clear();
			AllTasks.Clear();
            Start = tasks.FirstOrDefault();
			foreach (QuestTask task in tasks) { _tasks[task.TaskID] = task; AllTasks.Add(task); }
        }
    }

    public sealed class QuestCategoryInfo { public int Index { get; set; } }

    public static class QuestManager
    {
        public static List<Quest> Quests { get; } = new();
        public static bool Quiet { get; set; }
        public static int DeactivateCalls { get; private set; }
        public static int ActivateCalls { get; private set; }
        public static int UnlockCalls { get; private set; }
        public static int UnlockQuestBookCalls { get; private set; }
        public static bool QuestBookUnlocked { get; set; }
        public static Action<Quest> BeforeDeactivate;
        public static Action<Quest> BeforeActivate;
        public static Action<Quest> BeforeUnlock;
        public static Action BeforeUnlockQuestBook;
		public static Action<Quest> AfterDeactivate;
		public static Action<Quest> AfterActivate;
		public static Action<Quest> AfterUnlock;
		public static Action AfterUnlockQuestBook;

        public static Terraria.Localization.LocalizedText Localization(string key) => new(key + " {0} {1}");
        public static string LocalizationValue(string key) => key;
        public static QuestCategoryInfo GetCategoryInfo(string category) => new();
        public static void SayInChat(Terraria.Localization.LocalizedText text, Microsoft.Xna.Framework.Color color, bool force = false) { }
        public static void DeactivateQuest(Quest quest)
        {
            DeactivateCalls++;
            BeforeDeactivate?.Invoke(quest);
            quest.IsActive = false;
			AfterDeactivate?.Invoke(quest);
        }
        public static void ActivateQuest(Quest quest)
        {
            ActivateCalls++;
            BeforeActivate?.Invoke(quest);
            quest.IsActive = true;
			AfterActivate?.Invoke(quest);
        }
        public static void UnlockQuest(Quest quest, bool announce)
        {
            UnlockCalls++;
            BeforeUnlock?.Invoke(quest);
            quest.IsUnlocked = true;
			AfterUnlock?.Invoke(quest);
        }
        public static void UnlockQuestBook(bool announce)
        {
            UnlockQuestBookCalls++;
            BeforeUnlockQuestBook?.Invoke();
            QuestBookUnlocked = true;
			AfterUnlockQuestBook?.Invoke();
        }
        public static void Reset()
        {
            Quests.Clear();
            Quiet = false;
            DeactivateCalls = ActivateCalls = UnlockCalls = 0;
            UnlockQuestBookCalls = 0;
            QuestBookUnlocked = false;
            BeforeDeactivate = BeforeActivate = BeforeUnlock = null;
            BeforeUnlockQuestBook = null;
			AfterDeactivate = AfterActivate = AfterUnlock = null;
			AfterUnlockQuestBook = null;
        }
    }

    public sealed class StoredQuestData
    {
        public bool IsUnlocked;
        public bool IsActive;
        public bool IsCompleted;
        public bool RewardsGiven;
        public short TimeLeftActive;
        public short TimeLeftUnlocked;
        public byte[] Buffer;
    }

    public sealed class QuestWorld
    {
        public static Func<Quest, StoredQuestData> Store = _ => new StoredQuestData();
        public Dictionary<ushort, Queue<int>> NPCQuestQueue { get; } = new();
        public static StoredQuestData ToStoredQuest(Quest quest) => Store(quest);
    }

    public sealed class QuestGlobalNPC
    {
        public int ClientLootCalls { get; private set; }
        public Terraria.NPC LastNPC { get; private set; }
        public void ClientNPCLoot(Terraria.NPC npc) { ClientLootCalls++; LastNPC = npc; }
    }
}

internal static class TestHooks
{
    public static void Reset()
    {
        Terraria.Main.netMode = Terraria.ID.NetmodeID.SinglePlayer;
        Terraria.Main.myPlayer = 0;
        Terraria.Main.maxPlayers = 8;
        Terraria.Main.npc = Enumerable.Range(0, 256).Select(_ => new Terraria.NPC()).ToArray();
        global::SpiritMod.SpiritMod.Instance.Reset();
        global::SpiritMod.Mechanics.QuestSystem.QuestManager.Reset();
        global::SpiritMod.Mechanics.QuestSystem.QuestWorld.Store = _ => new global::SpiritMod.Mechanics.QuestSystem.StoredQuestData();
        Terraria.ModLoader.ModContent.ClearInstances();
    }
}
