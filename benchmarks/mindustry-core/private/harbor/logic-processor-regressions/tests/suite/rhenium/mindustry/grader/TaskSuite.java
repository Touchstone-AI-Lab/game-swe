package rhenium.mindustry.grader;

import mindustry.content.*;
import mindustry.game.*;
import mindustry.gen.*;
import mindustry.world.*;
import mindustry.world.blocks.logic.LogicBlock.*;
import mindustry.world.blocks.logic.MessageBlock.*;
import rhenium.mindustry.harness.*;

import static mindustry.Vars.*;

/** Hidden grader suite: logic processor regressions on the pinned v159.7 server. */
public class TaskSuite implements HarnessSuite{
    static final Team TEAM = Team.sharded;

    static LogicBuild processor(Ctx ctx, Block block, int x, int y, Building... links){
        Building placed = ctx.place(block, x, y, TEAM);
        Check.isTrue(placed instanceof LogicBuild, block.name + " is not a processor");
        LogicBuild processor = (LogicBuild)placed;
        for(Building link : links){
            processor.configureAny(link.pos());
        }
        return processor;
    }

    static MessageBuild message(Ctx ctx, int x, int y){
        Building placed = ctx.place(Blocks.message, x, y, TEAM);
        Check.isTrue(placed instanceof MessageBuild, "message block was not placed");
        return (MessageBuild)placed;
    }

    static String output(Ctx ctx, MessageBuild message, int frames){
        ctx.updateBlocks(frames);
        return message.message.toString();
    }

    static int countX(CharSequence text){
        int count = 0;
        for(int i = 0; i < text.length(); i++) if(text.charAt(i) == 'x') count++;
        return count;
    }

    static String prints(int characters){
        StringBuilder out = new StringBuilder();
        int remaining = characters;
        while(remaining > 0){
            int chunk = Math.min(40, remaining);
            out.append("print \"").append("x".repeat(chunk)).append("\"\n");
            remaining -= chunk;
        }
        return out.toString();
    }

    @Override
    public void define(Suite suite){
        suite.test("processor output reaches a linked message block", ctx -> {
            ctx.flatWorld(30, 30);
            MessageBuild message = message(ctx, 12, 10);
            LogicBuild processor = processor(ctx, Blocks.logicProcessor, 10, 10, message);
            processor.updateCode("print \"hello\"\nprint 7\nprintflush message1\n");
            Check.equal("hello7", output(ctx, message, 60), "message text");
        });

        suite.test("linked blocks are named after their block type", ctx -> {
            ctx.flatWorld(30, 30);
            Building conveyor = ctx.place(Blocks.conveyor, 12, 12, TEAM, 0);
            Building sorter = ctx.place(Blocks.sorter, 13, 12, TEAM);
            MessageBuild message = message(ctx, 12, 10);
            LogicBuild processor = processor(ctx, Blocks.logicProcessor, 10, 10, conveyor, sorter, message);
            processor.updateCode(
                "print conveyor1\nprint \" \"\nprint sorter1\nprint \" \"\nprint message1\n" +
                "print \" \"\nprint @links\nprintflush message1\n");
            Check.equal("conveyor sorter message 3", output(ctx, message, 60), "message text");
        });

        suite.test("sensor reads supported properties", ctx -> {
            ctx.flatWorld(30, 30);
            Building conveyor = ctx.place(Blocks.conveyor, 12, 12, TEAM, 0);
            MessageBuild message = message(ctx, 12, 10);
            LogicBuild processor = processor(ctx, Blocks.logicProcessor, 10, 10, conveyor, message);
            processor.updateCode(
                "sensor px conveyor1 @x\nsensor kind conveyor1 @type\nsensor copper conveyor1 @copper\n" +
                "sensor far 5 @x\n" +
                "print px\nprint \" \"\nprint kind\nprint \" \"\nprint copper\nprint \" \"\nprint far\n" +
                "printflush message1\n");
            Check.equal("12 conveyor 0 null", output(ctx, message, 80), "message text");
        });

        suite.test("sensor of an unsupported property yields null", ctx -> {
            ctx.flatWorld(30, 30);
            Building conveyor = ctx.place(Blocks.conveyor, 12, 12, TEAM, 0);
            MessageBuild message = message(ctx, 12, 10);
            LogicBuild processor = processor(ctx, Blocks.logicProcessor, 10, 10, conveyor, message);
            processor.updateCode(
                "set a 1\nsensor a @this null\nset b 2\nsensor b conveyor1 \"copper\"\n" +
                "print a\nprint \" \"\nprint b\nprintflush message1\n");
            Check.equal("null null", output(ctx, message, 80), "message text");
        });

        suite.test("format fills placeholders in order", ctx -> {
            ctx.flatWorld(30, 30);
            MessageBuild message = message(ctx, 12, 10);
            LogicBuild processor = processor(ctx, Blocks.logicProcessor, 10, 10, message);
            processor.updateCode("print \"{1} and {0}\"\nformat 5\nformat \"x\"\nprintflush message1\n");
            Check.equal("x and 5", output(ctx, message, 60), "message text");
        });

        suite.test("print output is capped at 400 characters", ctx -> {
            ctx.flatWorld(30, 30);
            MessageBuild message = message(ctx, 12, 10);
            LogicBuild processor = processor(ctx, Blocks.logicProcessor, 10, 10, message);
            processor.updateCode(prints(440) + "printflush message1\n");
            String text = output(ctx, message, 200);
            Check.equal(400, text.length(), "message length");
            Check.equal(400, countX(text), "filler characters");
        });

        suite.test("format fills a placeholder when the print buffer is full", ctx -> {
            ctx.flatWorld(30, 30);
            MessageBuild message = message(ctx, 12, 10);
            LogicBuild processor = processor(ctx, Blocks.logicProcessor, 10, 10, message);
            processor.updateCode("print \"{0}\"\n" + prints(397) + "format \"ok\"\nprintflush message1\n");
            String text = output(ctx, message, 200);
            Check.isTrue(text.startsWith("ok"), "message should start with the formatted value, got: " +
                text.substring(0, Math.min(12, text.length())));
            Check.equal(399, text.length(), "message length");
        });

        suite.test("a replaced linked block is reachable under its new name", ctx -> {
            ctx.flatWorld(30, 30);
            Building conveyor = ctx.place(Blocks.conveyor, 12, 12, TEAM, 0);
            MessageBuild message = message(ctx, 12, 10);
            LogicBuild processor = processor(ctx, Blocks.logicProcessor, 10, 10, conveyor, message);
            processor.updateCode(
                "print junction1\nprint \" \"\nprint conveyor1\nprint \" \"\nprint @links\nprintflush message1\n");
            Check.equal("null conveyor 2", output(ctx, message, 60), "message text before the replacement");
            ctx.tile(12, 12).setBlock(Blocks.junction, TEAM);
            Check.equal("junction null 2", output(ctx, message, 60), "message text after the replacement");
        });

        suite.test("other links keep their names when one linked block is replaced", ctx -> {
            ctx.flatWorld(30, 30);
            Building conveyor = ctx.place(Blocks.conveyor, 12, 12, TEAM, 0);
            Building sorter = ctx.place(Blocks.sorter, 13, 12, TEAM);
            MessageBuild message = message(ctx, 12, 10);
            LogicBuild processor = processor(ctx, Blocks.logicProcessor, 10, 10, conveyor, sorter, message);
            processor.updateCode("print sorter1\nprint \" \"\nprint message1\nprintflush message1\n");
            Check.equal("sorter message", output(ctx, message, 60), "message text before the replacement");
            ctx.tile(12, 12).setBlock(Blocks.junction, TEAM);
            Check.equal("sorter message", output(ctx, message, 60), "message text after the replacement");
        });

        suite.test("processor variables survive a save and reload", ctx -> {
            ctx.flatWorld(30, 30);
            MessageBuild message = message(ctx, 12, 10);
            LogicBuild processor = processor(ctx, Blocks.logicProcessor, 10, 10, message);
            String code =
                "jump 3 notEqual tag null\nset tag \"alpha\"\nset counter 100\nop add counter counter 1\n" +
                "print tag\nprint \":\"\nprint counter\nprintflush message1\n";
            processor.updateCode(code);
            String before = output(ctx, message, 120);
            Check.isTrue(before.startsWith("alpha:"), "message before saving: " + before);
            int saved = Integer.parseInt(before.substring("alpha:".length()));
            Check.isTrue(saved > 101, "the counter did not advance before saving: " + saved);
            ctx.saveAndReload();
            Building loaded = ctx.tile(10, 10).build;
            Check.isTrue(loaded instanceof LogicBuild, "the processor is missing after loading");
            Check.equal(code, ((LogicBuild)loaded).code, "processor code after loading");
            Building loadedMessage = ctx.tile(12, 10).build;
            Check.isTrue(loadedMessage instanceof MessageBuild, "the message block is missing after loading");
            String after = output(ctx, (MessageBuild)loadedMessage, 40);
            Check.isTrue(after.startsWith("alpha:"), "message after loading: " + after);
            int resumed = Integer.parseInt(after.substring("alpha:".length()));
            Check.isTrue(resumed > saved, "the counter restarted after loading: " + saved + " -> " + resumed);
        });

        suite.test("a world processor holding query results can be saved", ctx -> {
            ctx.flatWorld(30, 30);
            state.rules.allowEditWorldProcessors = true;
            MessageBuild message = message(ctx, 12, 10);
            LogicBuild processor = processor(ctx, Blocks.worldProcessor, 10, 10, message);
            String code = "query circle unit @sharded 10 10 5 5\nset held @queries\nset count 7\nprint count\nprintflush message1\n";
            processor.updateCode(code);
            Check.equal("7", output(ctx, message, 30), "world processor output before saving");
            try{
                ctx.saveAndReload();
            }catch(Throwable error){
                Throwable root = error;
                while(root.getCause() != null && root.getCause() != root) root = root.getCause();
                Check.fail("saving the world failed: " + root.getClass().getSimpleName() + ": " + root.getMessage());
            }
            Building loaded = ctx.tile(10, 10).build;
            Check.isTrue(loaded instanceof LogicBuild && loaded.block == Blocks.worldProcessor, "the world processor is missing after loading");
            Check.equal(code, ((LogicBuild)loaded).code, "world processor code after loading");
        });
    }
}
