package io.gamecodebench.harness;

import java.lang.reflect.Proxy;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import net.kyori.adventure.identity.Identity;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.entity.Player;

/** Best-effort {@link Player} stand-ins for player-free tests. */
public final class GcbProxies {

    private GcbProxies() {
    }

    /**
     * A proxy that answers identity, location, permission and messaging queries and throws
     * {@link UnsupportedOperationException} for everything else.
     */
    public static Player player(String name, UUID id, Location at) {
        PlayerHandler handler = new PlayerHandler(
            Objects.requireNonNull(name, "name"), Objects.requireNonNull(id, "id"),
            Objects.requireNonNull(at, "at").clone());
        return (Player) Proxy.newProxyInstance(
            GcbProxies.class.getClassLoader(), new Class<?>[] {Player.class}, handler);
    }

    /** Messages recorded by a proxy player; empty for any other player. */
    public static List<String> messages(Player player) {
        RecordingHandler handler = RecordingHandler.of(player);
        return handler == null ? List.of() : handler.messages();
    }

    /** Forgets the messages recorded by a proxy player. */
    public static void clearMessages(Player player) {
        RecordingHandler handler = RecordingHandler.of(player);
        if (handler != null) {
            handler.clear();
        }
    }

    private static final class PlayerHandler extends RecordingHandler {

        private final String name;
        private final UUID id;
        private final Location at;

        private PlayerHandler(String name, UUID id, Location at) {
            super("GcbProxies.player[" + name + "]");
            this.name = name;
            this.id = id;
            this.at = at;
        }

        @Override
        protected Object handle(String method, Object[] args) {
            return switch (method) {
                case "getName", "getDisplayName" -> name;
                case "name", "displayName" -> args.length == 0 ? Component.text(name) : UNSUPPORTED;
                case "getUniqueId" -> id;
                case "identity" -> Identity.identity(id);
                case "getLocation" -> location(args);
                case "getWorld" -> at.getWorld();
                case "hasPermission" -> true;
                case "isOp" -> false;
                case "isOnline" -> true;
                case "getGameMode" -> GameMode.SURVIVAL;
                case "getServer" -> Bukkit.getServer();
                default -> UNSUPPORTED;
            };
        }

        private Object location(Object[] args) {
            if (args.length == 1 && args[0] instanceof Location target) {
                // getLocation(Location) fills the caller's instance, mirroring Entity's contract.
                target.setWorld(at.getWorld());
                target.set(at.getX(), at.getY(), at.getZ());
                target.setYaw(at.getYaw());
                target.setPitch(at.getPitch());
                return target;
            }
            return at.clone();
        }
    }
}
