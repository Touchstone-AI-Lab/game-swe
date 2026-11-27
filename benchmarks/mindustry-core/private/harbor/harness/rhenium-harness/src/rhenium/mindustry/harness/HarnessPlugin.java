package rhenium.mindustry.harness;

import arc.*;
import mindustry.game.EventType.*;
import mindustry.mod.*;

/**
 * Trusted Rhenium harness plugin.
 *
 * <p>It is packaged together with one task's private grader suite and loaded from
 * {@code config/mods} of a real headless Mindustry server. Once the server has
 * finished loading, it runs the frozen cases on the main thread, prints exactly one
 * nonce-tagged result line and stops the server.</p>
 */
public class HarnessPlugin extends Plugin{
    @Override
    public void init(){
        String mode = System.getProperty("rhenium.harness.mode", "suite");
        String nonce = System.getProperty("rhenium.harness.nonce", "");
        Events.on(ServerLoadEvent.class, event -> Core.app.post(() -> Runner.start(mode, nonce, getClass().getClassLoader())));
    }
}
