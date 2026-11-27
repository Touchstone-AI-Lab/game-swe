package gcb;

import com.evacipated.cardcrawl.modthespire.ModInfo;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.lang.reflect.Method;

import static org.junit.jupiter.api.Assertions.*;

/**
 * How one mod is told apart from another: the identifier it is known by, when two
 * descriptions refer to the same mod, and how a declared requirement is resolved.
 */
public class ModIdentityTest {

    private static ModInfo mod(String id, String name) throws Exception {
        // the constructor is private, so build it the way deserialisation does
        java.lang.reflect.Constructor<ModInfo> c = ModInfo.class.getDeclaredConstructor();
        c.setAccessible(true);
        ModInfo m = c.newInstance();
        Field fid = ModInfo.class.getField("ID");
        Field fname = ModInfo.class.getField("Name");
        fid.set(m, id);
        fname.set(m, name);
        return m;
    }

    /** Positive control: an ordinary mod is known by its identifier. */
    @Test
    public void control_aNormalModIsKnownByItsId() throws Exception {
        assertEquals("com.example.mod", mod("com.example.mod", "Example").getIDName());
    }

    /** Positive control: a mod with no identifier at all is known by its name. */
    @Test
    public void control_aModWithoutAnIdIsKnownByItsName() throws Exception {
        assertEquals("Example", mod(null, "Example").getIDName());
    }

    /** A: an identifier that is present but blank is no identifier at all. */
    @Test
    public void aBlankIdentifierFallsBackToTheName() throws Exception {
        assertEquals("Example", mod("", "Example").getIDName(),
                "a blank id must not be used as the mod's name");
    }

    /** B: two different mods must stay different even if one has no identifier. */
    @Test
    public void aModWithAnIdIsNotTheSameAsOneWithout() throws Exception {
        ModInfo withId = mod("com.example.a", "Shared Name");
        ModInfo without = mod(null, "Shared Name");
        assertNotEquals(withId, without,
                "an identified mod and an unidentified one must not be treated as the same");
    }

    /** D: a requirement resolves to the first mod declaring that identifier. */
    @Test
    public void aRequirementResolvesToTheFirstMatch() throws Exception {
        ModInfo[] mods = new ModInfo[]{
                mod("com.example.dep", "Original"),
                mod("com.example.other", "Unrelated"),
                mod("com.example.dep", "Duplicate")
        };
        Method m = Class.forName("com.evacipated.cardcrawl.modthespire.Loader")
                .getDeclaredMethod("findDependencyIndex", ModInfo[].class, String.class);
        m.setAccessible(true);
        int idx = (int) m.invoke(null, mods, "com.example.dep");
        assertEquals(0, idx, "the first mod declaring the identifier must win, got index " + idx);
    }

    /** E: a version written the way mods actually write it is accepted. */
    @Test
    public void ordinaryVersionStringsAreAccepted() {
        assertDoesNotThrow(() -> ModInfo.safeVersion("1.0"),
                "a two-part version must be readable");
        assertDoesNotThrow(() -> ModInfo.safeVersion("2"),
                "a bare major version must be readable");
        assertEquals(1, ModInfo.safeVersion("1.2.3").getMajor().intValue(),
                "an ordinary three-part version must still parse");
    }
}
