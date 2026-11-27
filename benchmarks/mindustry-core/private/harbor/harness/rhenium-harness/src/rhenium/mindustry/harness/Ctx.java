package rhenium.mindustry.harness;

import arc.files.*;
import arc.util.*;
import mindustry.content.*;
import mindustry.core.GameState.*;
import mindustry.game.*;
import mindustry.gen.*;
import mindustry.io.*;
import mindustry.server.*;
import mindustry.world.*;

import java.util.*;
import java.util.regex.*;

import static mindustry.Vars.*;

/**
 * Helpers for one grader case. Everything runs on the server's main thread; the
 * world only advances when a case calls {@link #step(int)} or
 * {@link #updateBlocks(int)}, each frame lasting exactly one tick.
 */
public final class Ctx{
    private static final Pattern ANSI = Pattern.compile("\u001B\\[[0-9;]*[ -/]*[@-~]");

    final Fi scratch;
    private final int caseIndex;
    private int saves;

    Ctx(Fi scratch, int caseIndex){
        this.scratch = scratch;
        this.caseIndex = caseIndex;
    }

    /** A fresh {@code width}x{@code height} world of stone floor with default rules, in the playing state. */
    public void flatWorld(int width, int height){
        logic.reset();
        state.rules = new Rules();
        state.rules.limitMapArea = false;
        state.rules.waves = false;
        state.rules.waveTimer = false;
        state.rules.canGameOver = false;
        Tiles tiles = world.resize(width, height);
        world.beginMapLoad();
        for(int y = 0; y < height; y++){
            for(int x = 0; x < width; x++){
                tiles.set(x, y, new Tile(x, y, Blocks.stone, Blocks.air, Blocks.air));
            }
        }
        world.endMapLoad();
        state.set(State.playing);
    }

    public Tile tile(int x, int y){
        return Check.notNull(world.tile(x, y), "tile " + x + "," + y + " is outside the world");
    }

    /** Places {@code block} with its bottom-left-aware center at x,y and returns the new building. */
    public Building place(Block block, int x, int y, Team team, int rotation){
        Tile tile = tile(x, y);
        tile.setBlock(block, team, rotation);
        return Check.notNull(tile.build, block.name + " was not placed at " + x + "," + y);
    }

    public Building place(Block block, int x, int y, Team team){
        return place(block, x, y, team, 0);
    }

    /** Updates every building directly for {@code frames} ticks (no units, bullets or weather). */
    public void updateBlocks(int frames){
        for(Tile tile : world.tiles){
            if(tile.build != null && tile.isCenter()) tile.build.updateProximity();
        }
        for(int i = 0; i < frames; i++){
            Time.delta = 1f;
            Time.update();
            state.updateId++;
            for(Tile tile : world.tiles){
                if(tile.build != null && tile.isCenter()) tile.build.update();
            }
        }
    }

    /** Runs the full game logic (buildings, units, bullets, waves) for {@code frames} ticks. */
    public void step(int frames){
        if(!state.isGame()) Check.fail("the world is not in a playable state");
        for(int i = 0; i < frames; i++){
            Time.delta = 1f;
            logic.update();
        }
    }

    /** Runs one server console command and returns what it logged, without colours. */
    public String command(String line){
        ServerControl control = Check.notNull(ServerControl.instance, "the server console is not available");
        List<String> lines = captureLog(() -> control.handleCommandString(line));
        return String.join("\n", lines);
    }

    /** Everything logged while {@code action} runs, one entry per log call, without colours. */
    public List<String> captureLog(Runnable action){
        List<String> captured = new ArrayList<>();
        Log.LogHandler previous = Log.logger;
        Log.logger = (level, text) -> {
            captured.add(plain(text));
            previous.log(level, text);
        };
        try{
            action.run();
        }finally{
            Log.logger = previous;
        }
        return captured;
    }

    public static String plain(String text){
        return Log.removeColors(ANSI.matcher(text == null ? "" : text).replaceAll(""));
    }

    /** Writes the current world to a save file, resets the game and loads it back. */
    public void saveAndReload(){
        Fi file = scratch.child("case-" + caseIndex + "-save-" + (saves++) + ".msav");
        SaveIO.save(file);
        logic.reset();
        SaveIO.load(file);
        state.set(State.playing);
    }

    /** A file in this case's private scratch directory. */
    public Fi scratchFile(String name){
        return scratch.child("case-" + caseIndex + "-" + name);
    }
}
