package gcbtest.coinledger;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import net.kyori.adventure.identity.Identity;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.ComponentLike;
import net.kyori.adventure.text.minimessage.MiniMessage;
import net.kyori.adventure.text.serializer.legacy.LegacyComponentSerializer;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.command.CommandSender;
import org.bukkit.command.ConsoleCommandSender;
import org.bukkit.entity.Player;
import org.bukkit.permissions.Permission;

/**
 * A grader-owned command sender: a console-like sender with every permission, a sender that
 * holds only the permissions a case grants, or a player stand-in. Every message it receives
 * is recorded as trimmed plain-text lines.
 */
public final class Actor implements InvocationHandler {

    private enum Kind { CONSOLE, LIMITED, PLAYER }

    private final Kind kind;
    private final String name;
    private final UUID id;
    private final Set<String> permissions;
    private final List<String> lines = new ArrayList<>();
    private final CommandSender proxy;

    private Actor(Kind kind, String name, Set<String> permissions) {
        this.kind = kind;
        this.name = name;
        this.id = UUID.nameUUIDFromBytes(("OfflinePlayer:" + name).getBytes(StandardCharsets.UTF_8));
        this.permissions = Set.copyOf(permissions);
        Class<?> type = switch (kind) {
            case CONSOLE -> ConsoleCommandSender.class;
            case LIMITED -> CommandSender.class;
            case PLAYER -> Player.class;
        };
        this.proxy = (CommandSender) Proxy.newProxyInstance(Actor.class.getClassLoader(), new Class<?>[] {type}, this);
    }

    public static Actor console() {
        return new Actor(Kind.CONSOLE, "CONSOLE", Set.of());
    }

    public static Actor limited(String name, String... permissions) {
        return new Actor(Kind.LIMITED, name, Set.of(permissions));
    }

    public static Actor player(String name, String... permissions) {
        return new Actor(Kind.PLAYER, name, Set.of(permissions));
    }

    public CommandSender sender() {
        return proxy;
    }

    public Player player() {
        return (Player) proxy;
    }

    public String name() {
        return name;
    }

    public synchronized List<String> lines() {
        return List.copyOf(lines);
    }

    public synchronized void clear() {
        lines.clear();
    }

    /** Runs one command line as this sender and returns the lines it received. */
    public List<String> run(String line) {
        clear();
        Kit.dispatch(proxy, line);
        return lines();
    }

    private boolean has(String permission) {
        return kind == Kind.CONSOLE || permissions.contains(permission);
    }

    private synchronized void record(String plain) {
        for (String line : plain.split("\\R")) {
            lines.add(line.strip());
        }
    }

    private void recordArguments(String method, Object[] args) {
        if (args == null) {
            return;
        }
        for (Object arg : args) {
            if (arg instanceof String text) {
                record(switch (method) {
                    case "sendRichMessage" -> plain(MiniMessage.miniMessage().deserialize(text));
                    case "sendPlainMessage" -> text;
                    default -> plain(LegacyComponentSerializer.legacySection().deserialize(text));
                });
            } else if (arg instanceof String[] texts) {
                for (String text : texts) {
                    record(plain(LegacyComponentSerializer.legacySection().deserialize(text)));
                }
            } else if (arg instanceof ComponentLike component) {
                record(plain(component.asComponent()));
            }
        }
    }

    private static String plain(Component component) {
        return PlainTextComponentSerializer.plainText().serialize(component);
    }

    @Override
    public Object invoke(Object self, Method method, Object[] args) {
        String call = method.getName();
        if (method.getDeclaringClass() == Object.class) {
            return switch (call) {
                case "equals" -> self == args[0];
                case "hashCode" -> System.identityHashCode(self);
                default -> "Actor[" + kind + " " + name + "]";
            };
        }
        switch (call) {
            case "sendMessage", "sendPlainMessage", "sendRichMessage", "sendRawMessage" -> {
                recordArguments(call, args);
                return null;
            }
            case "getName" -> {
                return name;
            }
            case "name" -> {
                return Component.text(name);
            }
            case "hasPermission", "isPermissionSet" -> {
                Object key = args[0];
                return has(key instanceof Permission permission ? permission.getName() : String.valueOf(key));
            }
            case "isOp" -> {
                return kind == Kind.CONSOLE;
            }
            case "getServer" -> {
                return Bukkit.getServer();
            }
            default -> {
                // Player-only identity methods; everything else is unsupported by design.
            }
        }
        if (kind == Kind.PLAYER) {
            switch (call) {
                case "getUniqueId" -> {
                    return id;
                }
                case "identity" -> {
                    return Identity.identity(id);
                }
                case "getDisplayName", "getPlayerListName" -> {
                    return name;
                }
                case "displayName" -> {
                    if (args == null || args.length == 0) {
                        return Component.text(name);
                    }
                }
                case "isOnline" -> {
                    return true;
                }
                default -> {
                }
            }
        }
        if (kind == Kind.CONSOLE && call.equals("isConversing")) {
            return false;
        }
        throw new UnsupportedOperationException("grader " + kind.name().toLowerCase() + " sender does not support " + call);
    }
}
