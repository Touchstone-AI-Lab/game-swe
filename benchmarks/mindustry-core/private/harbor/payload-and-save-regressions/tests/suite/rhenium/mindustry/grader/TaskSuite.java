package rhenium.mindustry.grader;

import mindustry.content.*;
import mindustry.entities.units.*;
import mindustry.game.*;
import mindustry.gen.*;
import mindustry.world.*;
import mindustry.world.blocks.payloads.*;
import mindustry.world.blocks.payloads.PayloadConveyor.*;
import rhenium.mindustry.harness.*;

import static mindustry.Vars.*;

/** Hidden grader suite: payload and save regressions on the pinned v159.7 server. */
public class TaskSuite implements HarnessSuite{
    static final Team TEAM = Team.sharded;

    static PayloadConveyorBuild conveyor(Ctx ctx, int x, int y, Team team){
        Building build = ctx.place(Blocks.payloadConveyor, x, y, team, 0);
        Check.isTrue(build instanceof PayloadConveyorBuild, "payload conveyor was not placed");
        return (PayloadConveyorBuild)build;
    }

    static void carry(PayloadConveyorBuild conveyor, Block block, Team team){
        conveyor.handlePayload(conveyor, new BuildPayload(block, team));
        Check.notNull(conveyor.item, "the payload conveyor did not take the payload");
    }

    static void checkOnConveyor(PayloadConveyorBuild conveyor, Block block, String when){
        Check.notNull(conveyor.item, "the payload conveyor lost its payload " + when);
        Check.equal(block, conveyor.item.content(), "payload " + when);
        float dst = conveyor.item.dst(conveyor);
        Check.atMost(conveyor.block.size * tilesize, dst,
            "distance between the payload and its conveyor " + when + " (payload at " + conveyor.item.x() + "," + conveyor.item.y() + ")");
    }

    static Unit megaWith(Ctx ctx, float x, float y, Block block, Team team){
        Unit unit = UnitTypes.mega.spawn(TEAM, x, y);
        Check.isTrue(unit instanceof Payloadc, "mega cannot carry payloads");
        ((Payloadc)unit).addPayload(new BuildPayload(block, team));
        return unit;
    }

    static Unit polyWithPlans(Ctx ctx, int count){
        ctx.place(Blocks.coreShard, 10, 10, TEAM);
        Unit unit = UnitTypes.poly.spawn(TEAM, 200f, 200f);
        for(int i = 0; i < count; i++){
            unit.plans().addLast(new BuildPlan(20 + (i % 50), 20 + (i / 50), 0, Blocks.copperWall));
        }
        return unit;
    }

    @Override
    public void define(Suite suite){
        suite.test("payload blocks and units load on the pinned server", ctx -> {
            ctx.flatWorld(40, 40);
            PayloadConveyorBuild conveyor = conveyor(ctx, 20, 20, TEAM);
            carry(conveyor, Blocks.copperWall, TEAM);
            Unit unit = UnitTypes.mega.spawn(TEAM, 80f, 80f);
            Check.isTrue(unit instanceof Payloadc, "mega cannot carry payloads");
        });

        suite.test("payload conveyors pass payloads along", ctx -> {
            ctx.flatWorld(40, 40);
            PayloadConveyorBuild first = conveyor(ctx, 20, 20, TEAM);
            PayloadConveyorBuild second = conveyor(ctx, 23, 20, TEAM);
            carry(first, Blocks.copperWall, TEAM);
            ctx.updateBlocks(240);
            Check.isTrue(first.item == null, "the first conveyor still holds its payload");
            Check.notNull(second.item, "the payload did not reach the second conveyor");
        });

        suite.test("a team payload conveyor keeps its payload through a save", ctx -> {
            ctx.flatWorld(40, 40);
            carry(conveyor(ctx, 20, 20, TEAM), Blocks.copperWall, TEAM);
            ctx.updateBlocks(10);
            ctx.saveAndReload();
            ctx.updateBlocks(10);
            checkOnConveyor((PayloadConveyorBuild)ctx.tile(20, 20).build, Blocks.copperWall, "after loading");
        });

        suite.test("a derelict payload conveyor keeps its payload through a save", ctx -> {
            ctx.flatWorld(40, 40);
            PayloadConveyorBuild conveyor = conveyor(ctx, 20, 20, Team.derelict);
            carry(conveyor, Blocks.copperWall, Team.derelict);
            ctx.updateBlocks(10);
            checkOnConveyor(conveyor, Blocks.copperWall, "before saving");
            ctx.saveAndReload();
            ctx.updateBlocks(10);
            Building loaded = ctx.tile(20, 20).build;
            Check.isTrue(loaded instanceof PayloadConveyorBuild && loaded.team == Team.derelict, "the derelict conveyor is missing after loading");
            checkOnConveyor((PayloadConveyorBuild)loaded, Blocks.copperWall, "after loading");
        });

        suite.test("a builder's queued plans survive a save", ctx -> {
            ctx.flatWorld(80, 80);
            polyWithPlans(ctx, 40);
            ctx.saveAndReload();
            Unit loaded = Check.notNull(Groups.unit.find(u -> u.type == UnitTypes.poly), "the poly is missing after loading");
            Check.equal(40, loaded.plans().size, "queued plans after loading");
        });

        suite.test("a builder with more than a thousand queued plans survives a save", ctx -> {
            ctx.flatWorld(80, 80);
            polyWithPlans(ctx, 1200);
            ctx.saveAndReload();
            Unit loaded = Check.notNull(Groups.unit.find(u -> u.type == UnitTypes.poly), "the poly is missing after loading");
            Check.equal(1200, loaded.plans().size, "queued plans after loading");
        });

        suite.test("a unit sets down its own team's block near a core", ctx -> {
            ctx.flatWorld(80, 80);
            ctx.place(Blocks.coreShard, 20, 20, TEAM);
            Unit unit = megaWith(ctx, 30 * tilesize, 30 * tilesize, Blocks.copperWall, TEAM);
            Check.isTrue(((Payloadc)unit).dropLastPayload(), "the mega kept its payload");
            Tile tile = ctx.tile(30, 30);
            Check.equal(Blocks.copperWall, tile.block(), "block at the drop point");
            Check.equal(TEAM, tile.team(), "team at the drop point");
        });

        suite.test("a unit cannot set down an enemy block inside a core's protected area", ctx -> {
            ctx.flatWorld(80, 80);
            ctx.place(Blocks.coreShard, 20, 20, TEAM);
            Unit unit = megaWith(ctx, 30 * tilesize, 25 * tilesize, Blocks.copperWall, Team.crux);
            Check.isFalse(((Payloadc)unit).dropLastPayload(), "the enemy block was set down next to the core");
            Check.equal(Blocks.air, ctx.tile(30, 25).block(), "block at the drop point");
            Check.equal(1, ((Payloadc)unit).payloads().size, "payloads still carried");
        });

        suite.test("a unit sets down a derelict block far from any core", ctx -> {
            ctx.flatWorld(80, 80);
            ctx.place(Blocks.coreShard, 10, 10, TEAM);
            Unit unit = megaWith(ctx, 70 * tilesize, 70 * tilesize, Blocks.copperWall, Team.derelict);
            Check.isTrue(((Payloadc)unit).dropLastPayload(), "the mega kept its derelict payload");
            Check.equal(Team.derelict, ctx.tile(70, 70).team(), "team at the drop point");
        });

        suite.test("a unit can set down a carried derelict block near a core", ctx -> {
            ctx.flatWorld(80, 80);
            ctx.place(Blocks.coreShard, 20, 20, TEAM);
            Unit unit = megaWith(ctx, 30 * tilesize, 20 * tilesize, Blocks.copperWall, Team.derelict);
            Check.isTrue(((Payloadc)unit).dropLastPayload(), "the mega could not set down its derelict payload");
            Tile tile = ctx.tile(30, 20);
            Check.equal(Blocks.copperWall, tile.block(), "block at the drop point");
            Check.equal(Team.derelict, tile.team(), "team at the drop point");
        });
    }
}
