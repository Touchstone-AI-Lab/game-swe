package io.gamecodebench.harness;

import java.lang.reflect.Proxy;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.util.TriState;
import org.bukkit.Bukkit;

/** Creates player-free command senders. */
public final class GcbSenders {

    static final String NAME = "GCB";

    private GcbSenders() {
    }

    public static RecordingSender recording() {
        return (RecordingSender) Proxy.newProxyInstance(
            GcbSenders.class.getClassLoader(), new Class<?>[] {RecordingSender.class}, new SenderHandler());
    }

    private static final class SenderHandler extends RecordingHandler {

        private SenderHandler() {
            super("RecordingSender[" + NAME + "]");
        }

        @Override
        protected Object handle(String name, Object[] args) {
            return switch (name) {
                case "messages" -> messages();
                case "clear" -> {
                    clear();
                    yield null;
                }
                case "getName" -> NAME;
                case "name" -> Component.text(NAME);
                case "hasPermission", "isPermissionSet", "isOp" -> true;
                case "permissionValue" -> TriState.TRUE;
                case "setOp", "recalculatePermissions" -> null;
                case "isConversing" -> false;
                case "getServer" -> Bukkit.getServer();
                default -> UNSUPPORTED;
            };
        }
    }
}
