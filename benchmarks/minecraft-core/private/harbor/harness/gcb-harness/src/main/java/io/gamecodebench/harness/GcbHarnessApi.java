package io.gamecodebench.harness;

import java.io.File;
import java.lang.reflect.Modifier;
import java.net.URL;
import java.security.CodeSource;
import java.util.Enumeration;
import java.util.Objects;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;
import java.util.logging.Logger;
import org.bukkit.Bukkit;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;

/** Entry points used by the grader plugin. */
public final class GcbHarnessApi {

    private GcbHarnessApi() {
    }

    /** Registers one suite instance; invokes {@link GcbSuite#onEnable} before scanning its cases. */
    public static void register(JavaPlugin owner, GcbSuite suite) {
        CaseRegistry.register(Objects.requireNonNull(owner, "owner"), Objects.requireNonNull(suite, "suite"));
    }

    /** Scans the owner's jar for public, non-abstract {@link GcbSuite} classes with a public no-arg constructor. */
    public static void registerFromJar(JavaPlugin owner) {
        Objects.requireNonNull(owner, "owner");
        Logger log = owner.getLogger();
        ClassLoader loader = owner.getClass().getClassLoader();
        File jar = ownerJar(owner);
        int registered = 0;
        try (JarFile jarFile = new JarFile(jar)) {
            Enumeration<JarEntry> entries = jarFile.entries();
            while (entries.hasMoreElements()) {
                String className = className(entries.nextElement());
                if (className == null) {
                    continue;
                }
                Class<?> type;
                try {
                    type = Class.forName(className, false, loader);
                } catch (Throwable ignored) {
                    // Inner or optional classes may not be loadable; they cannot be suites anyway.
                    continue;
                }
                if (!isSuiteCandidate(type)) {
                    continue;
                }
                GcbSuite suite;
                try {
                    suite = (GcbSuite) type.getConstructor().newInstance();
                } catch (ReflectiveOperationException | RuntimeException | LinkageError thrown) {
                    log.severe("GCB could not instantiate suite " + className + ": " + thrown);
                    // Registering a placeholder is not possible; make the problem fatal via a synthetic suite.
                    register(owner, new BrokenSuite(className, thrown));
                    continue;
                }
                register(owner, suite);
                registered++;
            }
        } catch (java.io.IOException failure) {
            throw new IllegalStateException("cannot read grader jar " + jar, failure);
        }
        log.info("GCB registerFromJar found " + registered + " suite class(es) in " + jar.getName());
    }

    /** The enabled candidate plugin named by {@code gcb.candidate}. */
    public static Plugin candidate() {
        String name = System.getProperty("gcb.candidate", "");
        Plugin plugin = name.isEmpty() ? null : Bukkit.getPluginManager().getPlugin(name);
        if (plugin == null || !plugin.isEnabled()) {
            throw new IllegalStateException("candidate plugin is not enabled: " + name);
        }
        return plugin;
    }

    private static File ownerJar(JavaPlugin owner) {
        CodeSource source = owner.getClass().getProtectionDomain().getCodeSource();
        URL location = source == null ? null : source.getLocation();
        if (location == null) {
            throw new IllegalStateException("grader plugin has no code source location");
        }
        try {
            return new File(location.toURI());
        } catch (java.net.URISyntaxException | IllegalArgumentException failure) {
            throw new IllegalStateException("unusable grader jar location " + location, failure);
        }
    }

    private static String className(JarEntry entry) {
        String name = entry.getName();
        if (entry.isDirectory() || !name.endsWith(".class") || name.endsWith("module-info.class")) {
            return null;
        }
        return name.substring(0, name.length() - ".class".length()).replace('/', '.');
    }

    private static boolean isSuiteCandidate(Class<?> type) {
        int modifiers = type.getModifiers();
        if (!Modifier.isPublic(modifiers) || Modifier.isAbstract(modifiers) || type.isInterface()) {
            return false;
        }
        if (!GcbSuite.class.isAssignableFrom(type)) {
            return false;
        }
        try {
            return Modifier.isPublic(type.getConstructor().getModifiers());
        } catch (NoSuchMethodException missing) {
            return false;
        }
    }

    /** Stands in for a suite whose constructor failed so the failure surfaces as a fatal error. */
    private record BrokenSuite(String className, Throwable failure) implements GcbSuite {
        @Override
        public void onEnable(JavaPlugin grader) {
            throw new IllegalStateException("cannot instantiate " + className + ": " + failure, failure);
        }
    }
}
