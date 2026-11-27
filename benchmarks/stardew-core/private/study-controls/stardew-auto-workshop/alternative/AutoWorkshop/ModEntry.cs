using System.Collections.Generic;
using System.Linq;
using Microsoft.Xna.Framework;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;
using StardewValley.GameData.Machines;
using StardewValley.Inventories;
using StardewValley.Objects;
using SObject = StardewValley.Object;

namespace AutoWorkshop
{
    /// <summary>Study control (E0 "alternative"): an independent implementation of the public
    /// requirement. It is chest-centric and event-driven: every location keeps a list of
    /// "stations" (a machine plus every chest touching one of its four sides) which is rebuilt
    /// only when the world changes, and a short periodic pass services the stations.
    /// Locations are tracked per instance (NameOrUniqueName), so two coops never share
    /// stations. A product is moved only when the whole stack fits in a chest; otherwise it
    /// is left in the machine untouched.</summary>
    public sealed class ModEntry : Mod
    {
        /// <summary>A machine and the chests which touch it.</summary>
        private sealed class Station
        {
            public Station(SObject machine, Vector2 tile)
            {
                this.Machine = machine;
                this.Tile = tile;
            }

            public SObject Machine { get; }
            public Vector2 Tile { get; }
            public List<Chest> Chests { get; } = new();
        }

        /// <summary>The stations of one location instance.</summary>
        private sealed class Workshop
        {
            public Workshop(GameLocation location)
            {
                this.Location = location;
            }

            public GameLocation Location { get; }
            public List<Station> Stations { get; } = new();
        }

        private const uint ServiceInterval = 20;

        private static readonly Vector2[] Sides = { new(0, -1), new(1, 0), new(0, 1), new(-1, 0) };

        private readonly Dictionary<string, Workshop> Workshops = new();
        private readonly HashSet<string> StaleLocations = new();
        private bool EverythingStale = true;

        public override void Entry(IModHelper helper)
        {
            helper.Events.GameLoop.SaveLoaded += (_, _) => this.EverythingStale = true;
            helper.Events.GameLoop.DayStarted += (_, _) => this.EverythingStale = true;
            helper.Events.GameLoop.ReturnedToTitle += (_, _) => this.Forget();
            helper.Events.GameLoop.TimeChanged += (_, _) => this.EverythingStale = true; // safety net for changes no event reports
            helper.Events.World.LocationListChanged += (_, _) => this.EverythingStale = true;
            helper.Events.World.BuildingListChanged += (_, _) => this.EverythingStale = true;
            helper.Events.World.ObjectListChanged += (_, e) => this.StaleLocations.Add(e.Location.NameOrUniqueName);
            helper.Events.GameLoop.UpdateTicked += this.OnUpdateTicked;
        }

        private void Forget()
        {
            this.Workshops.Clear();
            this.StaleLocations.Clear();
            this.EverythingStale = true;
        }

        private void OnUpdateTicked(object? sender, UpdateTickedEventArgs e)
        {
            if (!Context.IsWorldReady || !Context.IsMainPlayer || !e.IsMultipleOf(ServiceInterval))
                return;

            this.RefreshStations();
            foreach (Workshop workshop in this.Workshops.Values)
            {
                foreach (Station station in workshop.Stations)
                    ServiceStation(workshop.Location, station);
            }
        }

        /*********
        ** Station index
        *********/
        private void RefreshStations()
        {
            if (this.EverythingStale)
            {
                this.Workshops.Clear();
                Utility.ForEachLocation(location =>
                {
                    this.Index(location);
                    return true;
                });
            }
            else if (this.StaleLocations.Count > 0)
            {
                foreach (string name in this.StaleLocations)
                {
                    GameLocation? location = this.Workshops.TryGetValue(name, out Workshop? known)
                        ? known.Location
                        : Game1.getLocationFromName(name);
                    this.Workshops.Remove(name);
                    if (location is not null)
                        this.Index(location);
                }
            }

            this.EverythingStale = false;
            this.StaleLocations.Clear();
        }

        private void Index(GameLocation location)
        {
            Workshop workshop = new(location);
            Dictionary<Vector2, Station> byMachineTile = new();

            // start from the chests: only a machine which touches one can ever become a station
            foreach ((Vector2 chestTile, SObject placed) in location.objects.Pairs)
            {
                if (placed is not Chest chest || !chest.playerChest.Value)
                    continue;

                foreach (Vector2 side in Sides)
                {
                    Vector2 machineTile = chestTile + side;
                    if (!location.objects.TryGetValue(machineTile, out SObject? neighbour) || !IsMachine(neighbour))
                        continue;

                    if (!byMachineTile.TryGetValue(machineTile, out Station? station))
                    {
                        station = new Station(neighbour, machineTile);
                        byMachineTile[machineTile] = station;
                        workshop.Stations.Add(station);
                    }
                    station.Chests.Add(chest);
                }
            }

            if (workshop.Stations.Count > 0)
                this.Workshops[location.NameOrUniqueName] = workshop;
        }

        private static bool IsMachine(SObject candidate)
        {
            return candidate is not Chest && candidate.GetMachineData() is not null;
        }

        /*********
        ** Servicing
        *********/
        private static void ServiceStation(GameLocation location, Station station)
        {
            SObject machine = station.Machine;

            // the index can be one pass behind the world; never touch something that moved
            if (!location.objects.TryGetValue(station.Tile, out SObject? current) || !ReferenceEquals(current, machine))
                return;

            if (machine.readyForHarvest.Value)
                Unload(machine, station.Chests);

            if (machine.heldObject.Value is null && !machine.readyForHarvest.Value)
                Load(machine, station.Chests);
        }

        private static void Unload(SObject machine, List<Chest> chests)
        {
            SObject? product = machine.heldObject.Value;

            // a product with no quantity can never be stored: throw it away so the machine is free again
            if (product is null || product.Stack <= 0)
            {
                ResetMachine(machine, collected: null);
                return;
            }

            foreach (Chest chest in chests)
            {
                if (!HasRoomForAll(chest, product))
                    continue;

                Item? rest = chest.addItem(product);
                if (rest is null || rest.Stack <= 0)
                {
                    ResetMachine(machine, collected: product);
                    return;
                }
                // unexpected partial transfer: what is left simply stays in the machine
            }
        }

        private static void Load(SObject machine, List<Chest> chests)
        {
            foreach (Chest chest in chests)
            {
                if (machine.AttemptAutoLoad(chest.GetItemsForPlayer(), Game1.player))
                    return;
            }
        }

        /// <summary>Whether the chest can take the whole stack, either by merging or in a free slot.</summary>
        private static bool HasRoomForAll(Chest chest, Item item)
        {
            IInventory slots = chest.GetItemsForPlayer();
            if (slots.Count(slot => slot is not null) < chest.GetActualCapacity())
                return true;

            int mergeRoom = slots
                .Where(slot => slot is not null && slot.canStackWith(item))
                .Sum(slot => slot.maximumStackSize() - slot.Stack);
            return mergeRoom >= item.Stack;
        }

        /// <summary>Empty the machine the way the game does after a player collects its product.</summary>
        private static void ResetMachine(SObject machine, Item? collected)
        {
            machine.heldObject.Value = null;
            machine.readyForHarvest.Value = false;
            machine.showNextIndex.Value = false;
            machine.ResetParentSheetIndex();

            // machines such as the crystalarium start their next cycle from the collected product
            MachineData? data = machine.GetMachineData();
            if (collected is not null && data is not null
                && MachineDataUtility.TryGetMachineOutputRule(machine, data, MachineOutputTrigger.OutputCollected, collected.getOne(), null, machine.Location, out MachineOutputRule rule, out _, out _, out _))
            {
                machine.OutputMachine(data, rule, machine.lastInputItem.Value, null, machine.Location, false);
            }
        }
    }
}
