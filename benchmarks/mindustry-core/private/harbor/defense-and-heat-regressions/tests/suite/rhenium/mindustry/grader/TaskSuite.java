package rhenium.mindustry.grader;

import arc.struct.*;
import mindustry.content.*;
import mindustry.game.*;
import mindustry.gen.*;
import mindustry.world.blocks.defense.turrets.Turret.*;
import mindustry.world.blocks.logic.LogicBlock.*;
import mindustry.world.blocks.logic.MessageBlock.*;
import rhenium.mindustry.harness.*;

import static mindustry.Vars.*;

/** Hidden grader suite: turret, heat and power regressions on the pinned v159.7 server. */
public class TaskSuite implements HarnessSuite{
    static final Team TEAM = Team.sharded, ENEMY = Team.crux;

    static TurretBuild duo(Ctx ctx, int x, int y){
        Building build = ctx.place(Blocks.duo, x, y, TEAM, 0);
        Check.isTrue(build instanceof TurretBuild, "duo was not placed");
        for(int i = 0; i < 20; i++) build.handleItem(null, Items.copper);
        return (TurretBuild)build;
    }

    /** Frame numbers (1-based) of every shot the turret fires during {@code frames} ticks. */
    static IntSeq shots(Ctx ctx, TurretBuild turret, int frames){
        IntSeq out = new IntSeq();
        int last = turret.totalShots;
        for(int i = 1; i <= frames; i++){
            ctx.step(1);
            if(turret.totalShots != last){
                for(int s = last; s < turret.totalShots; s++) out.add(i);
                last = turret.totalShots;
            }
        }
        return out;
    }

    static String heatOf(Ctx ctx, boolean disableFirst){
        ctx.flatWorld(40, 40);
        ctx.place(Blocks.heatSource, 5, 10, TEAM, 0);
        Building first = ctx.place(Blocks.heatRedirector, 7, 10, TEAM, 0);
        Building second = ctx.place(Blocks.heatRedirector, 10, 10, TEAM, 0);
        MessageBuild message = (MessageBuild)ctx.place(Blocks.message, 8, 14, TEAM);
        LogicBuild processor = (LogicBuild)ctx.place(Blocks.logicProcessor, 10, 14, TEAM);
        processor.configureAny(first.pos());
        processor.configureAny(second.pos());
        processor.configureAny(message.pos());
        processor.updateCode(
            "control enabled redirector1 " + (disableFirst ? 0 : 1) + "\n" +
            "sensor a redirector1 @heat\nsensor b redirector2 @heat\n" +
            "print a\nprint \" \"\nprint b\nprintflush message1\n");
        ctx.updateBlocks(240);
        return message.message.toString();
    }

    /** Two stationary enemy bullets around a powered shockwave tower: [0] at the offset, [1] 100 units east. */
    static Bullet[] shockwave(Ctx ctx, float dx, float dy){
        ctx.flatWorld(60, 60);
        state.rules.teams.get(TEAM).cheat = true;
        Building tower = ctx.place(Blocks.shockwaveTower, 30, 30, TEAM);
        var type = UnitTypes.dagger.weapons.first().bullet;
        Check.isTrue(type.hittable, "dagger bullets should be hittable");
        Bullet far = type.create(null, ENEMY, tower.x + dx, tower.y + dy, 0f, -1f, 0f, 20f, (Object)null);
        Bullet near = type.create(null, ENEMY, tower.x + 100f, tower.y, 0f, -1f, 0f, 20f, (Object)null);
        ctx.step(240);
        return new Bullet[]{far, near};
    }

    @Override
    public void define(Suite suite){
        suite.test("defense blocks load and update on the pinned server", ctx -> {
            ctx.flatWorld(40, 40);
            TurretBuild turret = duo(ctx, 10, 10);
            ctx.step(30);
            Check.isTrue(turret.hasAmmo(), "the duo holds no copper ammunition");
            Check.equal(0, turret.totalShots, "shots without a target");
        });

        suite.test("an engaged turret fires at its reload interval", ctx -> {
            ctx.flatWorld(40, 40);
            TurretBuild turret = duo(ctx, 10, 10);
            ctx.place(Blocks.thoriumWallLarge, 16, 10, ENEMY);
            IntSeq frames = shots(ctx, turret, 200);
            Check.atLeast(6, frames.size, "shots in 200 ticks");
            for(int i = 2; i < frames.size - 1; i++){
                int gap = frames.get(i + 1) - frames.get(i);
                Check.near(20, gap, 1, "ticks between shots " + (i + 1) + " and " + (i + 2));
            }
        });

        suite.test("an idle turret keeps its reload interval when it engages", ctx -> {
            ctx.flatWorld(40, 40);
            TurretBuild turret = duo(ctx, 10, 10);
            ctx.step(250);
            Check.equal(0, turret.totalShots, "shots while idle");
            ctx.place(Blocks.thoriumWallLarge, 16, 10, ENEMY);
            IntSeq frames = shots(ctx, turret, 120);
            Check.atLeast(3, frames.size, "shots after engaging");
            Check.atLeast(19, frames.get(1) - frames.get(0), "ticks between the first two shots after idling");
            Check.atLeast(19, frames.get(2) - frames.get(1), "ticks between the second and third shots after idling");
        });

        suite.test("a turret with faster ammunition keeps its average fire rate", ctx -> {
            ctx.flatWorld(40, 40);
            Building build = ctx.place(Blocks.duo, 10, 10, TEAM, 0);
            for(int i = 0; i < 20; i++) build.handleItem(null, Items.silicon);
            TurretBuild turret = (TurretBuild)build;
            ctx.place(Blocks.thoriumWallLarge, 16, 10, ENEMY);
            IntSeq frames = shots(ctx, turret, 360);
            Check.atLeast(20, frames.size, "shots in 360 ticks");
            int span = frames.peek() - frames.get(1);
            double average = span / (double)(frames.size - 2);
            Check.near(20.0 / 1.5, average, 0.15, "average ticks between shots with silicon (reload 20, silicon reloads 1.5x faster)");
        });

        suite.test("a loaded idle turret does not use its coolant", ctx -> {
            ctx.flatWorld(40, 40);
            TurretBuild turret = duo(ctx, 10, 10);
            turret.handleLiquid(null, Liquids.water, 5f);
            ctx.step(60);
            float settled = turret.liquids.get(Liquids.water);
            ctx.step(240);
            Check.near(settled, turret.liquids.get(Liquids.water), 0.0001, "water held by an idle, loaded duo");
        });

        suite.test("an enabled heat redirector passes heat on", ctx -> {
            String text = heatOf(ctx, false);
            String[] parts = text.split(" ");
            Check.equal(2, parts.length, "message '" + text + "'");
            Check.atLeast(100, Double.parseDouble(parts[1]), "heat of the second redirector");
        });

        suite.test("a disabled heat redirector passes no heat", ctx -> {
            String text = heatOf(ctx, true);
            String[] parts = text.split(" ");
            Check.equal(2, parts.length, "message '" + text + "'");
            Check.near(0, Double.parseDouble(parts[0]), 0.001, "heat of the disabled redirector");
            Check.near(0, Double.parseDouble(parts[1]), 0.001, "heat of the redirector behind it");
        });

        suite.test("a shockwave tower destroys enemy bullets inside its range", ctx -> {
            Bullet[] bullets = shockwave(ctx, 100f, 0f);
            Check.isFalse(bullets[0].isAdded(), "the enemy bullet 100 world units from the tower survived");
        });

        suite.test("a shockwave tower spares bullets outside its circular range", ctx -> {
            Bullet[] bullets = shockwave(ctx, 150f, 150f);
            Check.isFalse(bullets[1].isAdded(), "the enemy bullet 100 world units from the tower survived");
            Check.isTrue(bullets[0].isAdded(), "an enemy bullet 212 world units from the tower (range 170) was destroyed");
        });
    }
}
