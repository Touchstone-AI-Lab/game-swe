package com.evacipated.cardcrawl.modthespire;

import org.clapper.util.classutil.*;
import sun.reflect.ConstructorAccessor;
import sun.reflect.ReflectionFactory;
import java.io.File;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.net.URL;
import java.net.URLClassLoader;
import java.util.*;

/** Keeps the enum universe, named constants, query views and switch dispatch together. */
public class EnumBusterReflect {
    private final Class<?> type;
    private final Field universe;
    private final List<Field> dispatch;
    private final Deque<State> history = new ArrayDeque<>();

    public EnumBusterReflect(ClassLoader loader, Class<?> clazz) throws NoSuchFieldException, ClassNotFoundException {
        type = clazz;
        universe = clazz.getDeclaredField("$VALUES");
        universe.setAccessible(true);
        dispatch = discover(loader);
    }

    public Enum<?> make(String name) { return make(name, 0); }
    public Enum<?> make(String name, int ordinal) { return make(name, ordinal, new Class[0], new Object[0]); }
    public Enum<?> make(String name, int ordinal, Class[] extraTypes, Object[] extraValues) {
        try {
            history.push(new State());
            Class[] signature = new Class[extraTypes.length + 2];
            signature[0] = String.class; signature[1] = int.class;
            System.arraycopy(extraTypes, 0, signature, 2, extraTypes.length);
            Object[] args = new Object[extraValues.length + 2];
            args[0] = name; args[1] = ordinal;
            System.arraycopy(extraValues, 0, args, 2, extraValues.length);
            Constructor<?> constructor = type.getDeclaredConstructor(signature);
            ConstructorAccessor access = ReflectionFactory.getReflectionFactory().newConstructorAccessor(constructor);
            return (Enum<?>) type.cast(access.newInstance(args));
        } catch (Exception ex) { throw new IllegalArgumentException("Could not create enum", ex); }
    }

    public void addByValue(Enum<?> value) {
        try {
            State before = new State(); history.push(before);
            Enum<?>[] next = before.values.clone();
            int index = indexOf(next, value.name());
            if (index < 0) { index = next.length; next = Arrays.copyOf(next, next.length + 1); }
            next[index] = value;
            install(next, remap(before, next));
        } catch (Exception ex) { throw new IllegalArgumentException("Could not set the enum", ex); }
    }

    public boolean deleteByValue(Enum<?> value) {
        if (value == null) throw new NullPointerException();
        try {
            State before = new State(); history.push(before);
            int index = indexOf(before.values, value.name());
            if (index < 0) return false;
            Enum<?>[] next = Arrays.copyOf(before.values, before.values.length - 1);
            System.arraycopy(before.values, index + 1, next, index, next.length - index);
            install(next, remap(before, next));
            return true;
        } catch (Exception ex) { throw new IllegalArgumentException("Could not set the enum", ex); }
    }

    public boolean undo() {
        State state = history.poll();
        if (state == null) return false;
        try { install(state.values.clone(), state.maps); return true; }
        catch (Exception ex) { throw new IllegalStateException("Could not undo", ex); }
    }
    public void restore() { while (undo()) { } }

    private static int indexOf(Enum<?>[] values, String name) {
        for (int i = 0; i < values.length; i++) if (values[i].name().equals(name)) return i;
        return -1;
    }

    private Map<Field, int[]> remap(State before, Enum<?>[] next) {
        Map<Field, int[]> result = new LinkedHashMap<>();
        for (Map.Entry<Field, int[]> entry : before.maps.entrySet()) {
            int[] mapped = new int[next.length];
            for (int i = 0; i < next.length; i++) {
                int previous = indexOf(before.values, next[i].name());
                if (previous >= 0 && previous < entry.getValue().length) mapped[i] = entry.getValue()[previous];
            }
            result.put(entry.getKey(), mapped);
        }
        return result;
    }

    private void install(Enum<?>[] values, Map<Field, int[]> maps) throws Exception {
        Field ordinal = Enum.class.getDeclaredField("ordinal"); ordinal.setAccessible(true);
        Map<String, Enum<?>> directory = new HashMap<>();
        for (int i = 0; i < values.length; i++) { ordinal.setInt(values[i], i); directory.put(values[i].name(), values[i]); }
        ReflectionHelper.setStaticFinalField(universe, values);
        for (Field constant : type.getDeclaredFields()) {
            if (constant.getType() == type && java.lang.reflect.Modifier.isStatic(constant.getModifiers()) && constant.isEnumConstant()) {
                constant.setAccessible(true);
                ReflectionHelper.setStaticFinalField(constant, directory.get(constant.getName()));
            }
        }
        for (Map.Entry<Field, int[]> entry : maps.entrySet()) ReflectionHelper.setStaticFinalField(entry.getKey(), entry.getValue().clone());
        Field constants = Class.class.getDeclaredField("enumConstants"); constants.setAccessible(true); constants.set(type, values.clone());
        Field names = Class.class.getDeclaredField("enumConstantDirectory"); names.setAccessible(true); names.set(type, directory);
    }

    private class State {
        final Enum<?>[] values;
        final Map<Field, int[]> maps = new LinkedHashMap<>();
        State() throws IllegalAccessException {
            values = ((Enum<?>[]) universe.get(null)).clone();
            for (Field field : dispatch) maps.put(field, ((int[]) field.get(null)).clone());
        }
    }

    private List<Field> discover(ClassLoader loader) throws ClassNotFoundException, NoSuchFieldException {
        Set<File> paths = new LinkedHashSet<>(); paths.add(new File(Loader.STS_JAR));
        if (Loader.MODINFOS != null) for (ModInfo mod : Loader.MODINFOS) addPath(paths, mod.jarURL);
        for (ClassLoader cursor = loader; cursor != null; cursor = cursor.getParent()) {
            if (cursor instanceof URLClassLoader) for (URL url : ((URLClassLoader) cursor).getURLs()) addPath(paths, url);
        }
        ClassFinder finder = new ClassFinder(); for (File file : paths) finder.add(file);
        Collection<ClassInfo> classes = new ArrayList<>(); finder.findClasses(classes);
        String wanted = "$SwitchMap$" + type.getName().replace('.', '$');
        Set<Field> matches = new LinkedHashSet<>();
        for (ClassInfo info : classes) for (FieldInfo field : info.getFields()) {
            if (wanted.equals(field.getName())) {
                Field found = loader.loadClass(info.getClassName()).getDeclaredField(wanted);
                found.setAccessible(true); matches.add(found);
            }
        }
        return new ArrayList<>(matches);
    }

    private static void addPath(Set<File> paths, URL url) {
        if (url != null && "file".equals(url.getProtocol())) {
            try { paths.add(new File(url.toURI())); }
            catch (java.net.URISyntaxException ex) { throw new IllegalArgumentException(ex); }
        }
    }
}
