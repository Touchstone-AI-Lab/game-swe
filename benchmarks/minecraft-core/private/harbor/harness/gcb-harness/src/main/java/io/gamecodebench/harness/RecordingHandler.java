package io.gamecodebench.harness;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.List;
import net.kyori.adventure.text.ComponentLike;
import net.kyori.adventure.text.serializer.legacy.LegacyComponentSerializer;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;

/**
 * Shared invocation handler for the harness proxies: records every message-sending call as
 * plain text, answers {@link Object} methods sanely, and rejects anything the subclass does
 * not explicitly support.
 */
abstract class RecordingHandler implements InvocationHandler {

    /** Returned by {@link #handle} when a method is not supported. */
    protected static final Object UNSUPPORTED = new Object();

    private final String label;
    private final List<String> messages = new ArrayList<>();

    protected RecordingHandler(String label) {
        this.label = label;
    }

    /** The handler behind a harness proxy, or null for any other object. */
    static RecordingHandler of(Object candidate) {
        if (candidate != null && Proxy.isProxyClass(candidate.getClass())
            && Proxy.getInvocationHandler(candidate) instanceof RecordingHandler handler) {
            return handler;
        }
        return null;
    }

    // Commands such as /version report asynchronously, so the log must be thread-safe.
    synchronized List<String> messages() {
        return List.copyOf(messages);
    }

    synchronized void clear() {
        messages.clear();
    }

    synchronized void record(String message) {
        messages.add(message);
    }

    @Override
    public final Object invoke(Object proxy, Method method, Object[] args) {
        String name = method.getName();
        if (method.getDeclaringClass() == Object.class) {
            return switch (name) {
                case "equals" -> proxy == args[0];
                case "hashCode" -> System.identityHashCode(proxy);
                default -> toString();
            };
        }
        if (name.equals("sendMessage") || name.equals("sendPlainMessage")
            || name.equals("sendRichMessage") || name.equals("sendRawMessage")) {
            recordArguments(args);
            return null;
        }
        Object result = handle(name, args == null ? new Object[0] : args);
        if (result == UNSUPPORTED) {
            throw new UnsupportedOperationException(label + " does not support " + name);
        }
        return result;
    }

    /** Answers one interface method or returns {@link #UNSUPPORTED}. */
    protected abstract Object handle(String name, Object[] args);

    @Override
    public String toString() {
        return label;
    }

    private void recordArguments(Object[] args) {
        if (args == null) {
            return;
        }
        for (Object arg : args) {
            if (arg instanceof String text) {
                record(plain(text));
            } else if (arg instanceof String[] lines) {
                for (String line : lines) {
                    record(plain(line));
                }
            } else if (arg instanceof ComponentLike component) {
                record(plain(component));
            }
        }
    }

    static String plain(ComponentLike component) {
        return PlainTextComponentSerializer.plainText().serialize(component.asComponent());
    }

    /** Legacy strings are normalised through the section serializer so colour codes drop out. */
    static String plain(String legacy) {
        return legacy.indexOf(LegacyComponentSerializer.SECTION_CHAR) < 0
            ? legacy
            : plain(LegacyComponentSerializer.legacySection().deserialize(legacy));
    }
}
