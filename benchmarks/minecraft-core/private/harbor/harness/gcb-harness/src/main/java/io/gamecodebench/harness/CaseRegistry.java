package io.gamecodebench.harness;

import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.logging.Logger;
import org.bukkit.plugin.java.JavaPlugin;

/**
 * Process-wide registry of cases. Registration problems (duplicate names, bad signatures,
 * failing suite setup) are remembered instead of thrown so that the harness can report them
 * as a fatal envelope rather than leaving the grader plugin half-enabled.
 */
final class CaseRegistry {

    private static final List<GcbCaseRecord> CASES = new ArrayList<>();
    private static final Set<String> NAMES = new HashSet<>();
    private static String fatal;

    private CaseRegistry() {
    }

    static synchronized void register(JavaPlugin owner, GcbSuite suite) {
        Logger log = owner.getLogger();
        String suiteName = suite.getClass().getName();
        try {
            suite.onEnable(owner);
        } catch (Throwable thrown) {
            recordFatal(log, "suite " + suiteName + " onEnable failed: " + CaseResult.describe(thrown));
            return;
        }
        int count = 0;
        for (Method method : caseMethods(suite.getClass())) {
            GcbCase annotation = method.getAnnotation(GcbCase.class);
            String problem = validate(method);
            if (problem != null) {
                recordFatal(log, "case " + annotation.value() + " on " + suiteName + " " + problem);
                continue;
            }
            if (!NAMES.add(annotation.value())) {
                recordFatal(log, "duplicate case name: " + annotation.value());
                continue;
            }
            CASES.add(new GcbCaseRecord(annotation.value(), annotation.order(), annotation.ticks(), suite, method));
            count++;
        }
        log.info("GCB registered " + count + " case(s) from " + suiteName);
    }

    static synchronized List<GcbCaseRecord> sortedCases() {
        List<GcbCaseRecord> sorted = new ArrayList<>(CASES);
        sorted.sort(Comparator.comparingInt(GcbCaseRecord::order).thenComparing(GcbCaseRecord::name));
        return sorted;
    }

    static synchronized String fatalError() {
        return fatal;
    }

    private static void recordFatal(Logger log, String message) {
        log.severe("GCB registration error: " + message);
        if (fatal == null) {
            fatal = message;
        }
    }

    // Walk the class hierarchy explicitly so that a non-public annotated method is reported
    // instead of silently ignored (getMethods() would only show public ones).
    private static List<Method> caseMethods(Class<?> type) {
        List<Method> found = new ArrayList<>();
        for (Class<?> current = type; current != null && current != Object.class; current = current.getSuperclass()) {
            for (Method method : current.getDeclaredMethods()) {
                if (method.isAnnotationPresent(GcbCase.class) && !method.isSynthetic()) {
                    found.add(method);
                }
            }
        }
        return found;
    }

    private static String validate(Method method) {
        if (!Modifier.isPublic(method.getModifiers())) {
            return "must be public";
        }
        if (Modifier.isStatic(method.getModifiers())) {
            return "must not be static";
        }
        Class<?>[] params = method.getParameterTypes();
        if (params.length == 0 || (params.length == 1 && params[0] == GcbScript.class)) {
            return null;
        }
        return "must take no parameters or a single GcbScript";
    }
}
