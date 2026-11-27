package rhenium.mindustry.grader;

import arc.*;
import arc.files.*;
import mindustry.content.*;
import mindustry.mod.data.*;
import mindustry.type.*;
import mindustry.world.blocks.defense.*;
import rhenium.mindustry.harness.*;

import static mindustry.Vars.*;

/** Hidden grader suite: dedicated-server data patch regressions on the pinned v159.7 server. */
public class TaskSuite implements HarnessSuite{
    static final String MAP = "Ancient_Caldera";

    static Fi assets(){
        return Core.settings.getDataDirectory().child("assets");
    }

    /** Removes every server asset file and reloads the (now empty) asset list. */
    static void clearAssets(Ctx ctx){
        if(state.isGame()) ctx.command("stop");
        assets().child("patches").emptyDirectory();
        for(Fi folder : assets().child("content").list()){
            if(folder.isDirectory()) folder.emptyDirectory();
        }
        ctx.command("reloadassets");
    }

    static void write(String path, String json){
        assets().child(path).writeString(json);
    }

    static String host(Ctx ctx){
        String out = ctx.command("host " + MAP);
        Check.isTrue(state.isGame(), "host " + MAP + " did not start a game: " + out);
        return out;
    }

    /** The item defined by content/items/rhenium-alloy.json; data-asset content carries the dp- prefix. */
    static Item alloy(){
        return content.item("dp-rhenium-alloy");
    }

    static PatchAsset patchNamed(String name){
        return state.data.getPatches().find(p -> name.equals(p.name));
    }

    static String patchNames(){
        StringBuilder out = new StringBuilder();
        for(PatchAsset patch : state.data.getPatches()){
            if(out.length() > 0) out.append(", ");
            out.append(patch.name);
        }
        return "[" + out + "]";
    }

    @Override
    public void define(Suite suite){
        suite.test("the server loads patch files from its asset folder", ctx -> {
            clearAssets(ctx);
            write("patches/duo-health.json", "{\"name\": \"duo-health\", \"block\": {\"duo\": {\"health\": 777}}}");
            String out = ctx.command("reloadassets");
            Check.isTrue(out.contains("Loaded 1 data asset files."), "reloadassets output: " + out);
            clearAssets(ctx);
        });

        suite.test("a patch changes a block while its map is hosted", ctx -> {
            clearAssets(ctx);
            float original = Blocks.duo.health;
            write("patches/duo-health.json", "{\"name\": \"duo-health\", \"block\": {\"duo\": {\"health\": 777}}}");
            ctx.command("reloadassets");
            host(ctx);
            Check.near(777, Blocks.duo.health, 0.001, "duo health while patched");
            PatchAsset patch = Check.notNull(patchNamed("duo-health"), "active patches: " + patchNames());
            Check.isFalse(patch.error, "the patch reported an error: " + patch.warnings);
            clearAssets(ctx);
            host(ctx);
            Check.near(original, Blocks.duo.health, 0.001, "duo health after hosting without the patch");
            clearAssets(ctx);
        });

        suite.test("a server-defined item can be used by a patch", ctx -> {
            clearAssets(ctx);
            write("content/items/rhenium-alloy.json", "{\"color\": \"ff00ff\", \"cost\": 2}");
            write("patches/alloy-duo.json",
                "{\"name\": \"alloy-duo\", \"block\": {\"duo\": {\"requirements\": [\"dp-rhenium-alloy/7\", \"copper/5\"]}}}");
            ctx.command("reloadassets");
            host(ctx);
            Item alloy = Check.notNull(alloy(), "the server-defined item is missing");
            PatchAsset patch = Check.notNull(patchNamed("alloy-duo"), "active patches: " + patchNames());
            Check.isFalse(patch.error, "the patch failed: " + patch.warnings);
            Check.isTrue(patch.warnings.isEmpty(), "the patch reported warnings: " + patch.warnings);
            Check.equal(2, Blocks.duo.requirements.length, "duo requirement count");
            Check.equal(alloy, Blocks.duo.requirements[0].item, "first duo requirement");
            Check.equal(7, Blocks.duo.requirements[0].amount, "first duo requirement amount");
            clearAssets(ctx);
        });

        suite.test("a server-defined item exists while its map is hosted", ctx -> {
            clearAssets(ctx);
            write("content/items/rhenium-alloy.json", "{\"color\": \"ff00ff\", \"cost\": 2}");
            ctx.command("reloadassets");
            host(ctx);
            Item alloy = Check.notNull(alloy(), "the server-defined item is missing");
            Check.near(2, alloy.cost, 0.001, "cost of the server-defined item");
            clearAssets(ctx);
        });

        suite.test("patching a build tower also changes the drones it builds with", ctx -> {
            clearAssets(ctx);
            BuildTurret tower = (BuildTurret)Blocks.buildTower;
            float speed = tower.buildSpeed, range = tower.range;
            write("patches/build-tower.json",
                "{\"name\": \"build-tower\", \"block\": {\"build-tower\": {\"buildSpeed\": 3.5, \"range\": 300}}}");
            ctx.command("reloadassets");
            host(ctx);
            Check.near(3.5, tower.buildSpeed, 0.001, "patched build tower buildSpeed");
            Check.near(3.5, tower.unitType.buildSpeed, 0.001, "build speed of the tower's builder unit");
            Check.near(300, tower.unitType.buildRange, 0.001, "build range of the tower's builder unit");
            clearAssets(ctx);
            host(ctx);
            Check.near(speed, tower.unitType.buildSpeed, 0.001, "builder unit speed after hosting without the patch");
            Check.near(range, tower.unitType.buildRange, 0.001, "builder unit range after hosting without the patch");
            clearAssets(ctx);
        });

        suite.test("a planet-restricted patch applies on its planet", ctx -> {
            clearAssets(ctx);
            write("patches/serpulo-only.json",
                "{\"name\": \"serpulo-only\", \"requiredPlanets\": [\"serpulo\"], \"block\": {\"scatter\": {\"health\": 1234}}}");
            ctx.command("reloadassets");
            host(ctx);
            Check.equal("serpulo", state.rules.planet.name, "planet of the hosted map");
            Check.near(1234, Blocks.scatter.health, 0.001, "scatter health");
            Check.notNull(patchNamed("serpulo-only"), "active patches: " + patchNames());
            clearAssets(ctx);
        });

        suite.test("a patch for another planet is neither applied nor listed", ctx -> {
            clearAssets(ctx);
            float health = Blocks.duo.health;
            write("patches/erekir-only.json",
                "{\"name\": \"erekir-only\", \"requiredPlanets\": [\"erekir\"], \"block\": {\"duo\": {\"health\": 4321}}}");
            write("patches/duo-armor.json", "{\"name\": \"duo-armor\", \"block\": {\"duo\": {\"armor\": 3}}}");
            ctx.command("reloadassets");
            host(ctx);
            Check.near(health, Blocks.duo.health, 0.001, "duo health on a serpulo map");
            Check.near(3, Blocks.duo.armor, 0.001, "duo armor from the unrestricted patch");
            Check.equal(1, state.data.getPatches().size, "number of active patches " + patchNames());
            Check.notNull(patchNamed("duo-armor"), "active patches: " + patchNames());
            clearAssets(ctx);
        });
    }
}
