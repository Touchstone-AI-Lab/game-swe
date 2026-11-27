package gcb;

import com.evacipated.cardcrawl.modthespire.ModInfo;
import org.junit.jupiter.api.Test;

import java.io.*;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;

import static org.junit.jupiter.api.Assertions.*;

/**
 * What survives when a mod's description is written down and read back.
 * The loader caches these records between runs, so anything that does not round-trip
 * comes back wrong on the next start-up.
 */
public class ModRecordTest {

    private static ModInfo build() throws Exception {
        Constructor<ModInfo> c = ModInfo.class.getDeclaredConstructor();
        c.setAccessible(true);
        ModInfo m = c.newInstance();
        set(m, "ID", "com.example.mod");
        set(m, "Name", "Example Mod");
        set(m, "Authors", new String[]{"Ada"});
        set(m, "Credits", "art by Bob");
        set(m, "Description", "does a thing");
        set(m, "STS_Version", "2023-05-22");
        set(m, "Dependencies", new String[]{"basemod"});
        set(m, "OptionalDependencies", new String[]{"stslib"});
        set(m, "UpdateJSON", null);
        set(m, "ModVersion", ModInfo.safeVersion("1.2.3"));
        set(m, "MTS_Version", ModInfo.safeVersion("3.30.3"));
        return m;
    }

    private static void set(ModInfo m, String field, Object v) throws Exception {
        Field f = ModInfo.class.getField(field);
        f.set(m, v);
    }

    private static ModInfo roundTrip(ModInfo in) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
            out.writeObject(in);
        }
        try (ObjectInputStream i = new ObjectInputStream(new ByteArrayInputStream(bytes.toByteArray()))) {
            return (ModInfo) i.readObject();
        }
    }

    /** Positive control: writing a record down and reading it back works at all. */
    @Test
    public void control_aRecordSurvivesBeingWrittenDown() throws Exception {
        ModInfo back = roundTrip(build());
        assertNotNull(back, "a stored record must come back");
        assertEquals("com.example.mod", back.ID, "the identifier must survive");
        assertEquals("Example Mod", back.Name, "the title must survive");
    }

    /** C: a version written the lenient way must be readable the same way. */
    @Test
    public void aTwoPartVersionSurvivesTheRoundTrip() throws Exception {
        ModInfo m = build();
        set(m, "MTS_Version", ModInfo.safeVersion("3.30"));
        ModInfo back = assertDoesNotThrow(() -> roundTrip(m),
                "a version the loader itself accepts must be readable again");
        assertEquals(3, back.MTS_Version.getMajor().intValue());
    }

    /** D: everything the descriptor carries must survive, not only some of it. */
    @Test
    public void theWholeRecordSurvives() throws Exception {
        ModInfo back = roundTrip(build());
        assertArrayEquals(new String[]{"Ada"}, back.Authors,
                "the author list came back as: " + java.util.Arrays.toString(back.Authors));
        assertEquals("2023-05-22", back.STS_Version, "the game version must survive");
        assertEquals("1.2.3", back.ModVersion.toString(), "the mod version must survive");
    }

    /** A mod keeps its identity across a rename: the identifier is what identifies it. */
    @Test
    public void aRenamedModIsStillTheSameMod() throws Exception {
        ModInfo before = build();
        ModInfo after = build();
        Field f = ModInfo.class.getField("Name");
        f.set(after, "Example Mod (2024 Edition)");
        assertEquals(before, after,
                "the same identifier means the same mod even when the title changes");
    }

    /** A version written the way the loader itself accepts must survive storage. */
    @Test
    public void aLenientVersionSurvivesStorage() throws Exception {
        ModInfo m = build();
        Field f = ModInfo.class.getField("ModVersion");
        f.set(m, ModInfo.safeVersion("2.1"));
        ModInfo back = assertDoesNotThrow(() -> roundTrip(m),
                "a version the loader accepts must be readable again");
        assertEquals(2, back.ModVersion.getMajor().intValue());
    }

    /** Records with no identifier are told apart by title, so both must count. */
    @Test
    public void unidentifiedRecordsAreToldApartByTitle() throws Exception {
        Constructor<ModInfo> c = ModInfo.class.getDeclaredConstructor();
        c.setAccessible(true);
        ModInfo a = c.newInstance(); ModInfo b = c.newInstance();
        ModInfo.class.getField("Name").set(a, "First");
        ModInfo.class.getField("Name").set(b, "Second");
        assertNotEquals(a, b, "different titles must not be the same record");
        java.util.Set<ModInfo> set = new java.util.HashSet<>();
        set.add(a); set.add(b);
        assertEquals(2, set.size(),
                "two different unidentified records must both be kept, got " + set.size());
    }
}
