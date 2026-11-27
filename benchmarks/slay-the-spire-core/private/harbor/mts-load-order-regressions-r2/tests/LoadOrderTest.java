package gcb;

import com.evacipated.cardcrawl.modthespire.GraphTS;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.HashSet;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * The order the loader initialises mods in.
 *
 * Convention taken from the loader itself, not assumed: it calls
 *   addEdge(indexOfDependency, indexOfDependent)
 * and then tsortStable(). tsort() is never called anywhere in the project, so only the
 * stable sort is exercised here.
 */
public class LoadOrderTest {

    private static GraphTS<String> graph(String... names) {
        GraphTS<String> g = new GraphTS<>();
        for (String n : names) g.addVertex(n);
        return g;
    }

    /** Positive control: with no dependencies declared, every mod survives in order. */
    @Test
    public void control_everyModSurvivesWithNoDependencies() throws Exception {
        GraphTS<String> g = graph("a", "b", "c");
        g.tsortStable();
        assertEquals(Arrays.asList("a", "b", "c"), g.sortedArray,
                "with nothing declared the order must be untouched");
    }

    /** Positive control: nothing is lost or duplicated. */
    @Test
    public void control_nothingIsLostOrDuplicated() throws Exception {
        GraphTS<String> g = graph("a", "b", "c", "d");
        g.addEdge(1, 0);
        g.addEdge(3, 2);
        g.tsortStable();
        assertEquals(4, g.sortedArray.size(), "every mod must appear");
        assertEquals(4, new HashSet<>(g.sortedArray).size(), "and only once");
    }

    /** A mod listed as a dependency must be initialised before the mod that needs it. */
    @Test
    public void aDependencyIsInitialisedBeforeItsDependent() throws Exception {
        // "dependent" declares a dependency on "base"; the loader adds base -> dependent
        GraphTS<String> g = graph("dependent", "base");
        g.addEdge(1, 0);
        g.tsortStable();
        List<String> order = g.sortedArray;
        assertTrue(order.indexOf("base") < order.indexOf("dependent"),
                "the dependency must load first, got " + order);
    }

    /** A chain of dependencies resolves end to end, not just pairwise. */
    @Test
    public void aChainOfDependenciesResolves() throws Exception {
        GraphTS<String> g = graph("top", "middle", "bottom");
        g.addEdge(1, 0);   // middle -> top
        g.addEdge(2, 1);   // bottom -> middle
        g.tsortStable();
        List<String> order = g.sortedArray;
        assertTrue(order.indexOf("bottom") < order.indexOf("middle")
                && order.indexOf("middle") < order.indexOf("top"),
                "a chain must resolve bottom-up, got " + order);
    }

    /** Two mods that declare each other must be left in their original order. */
    @Test
    public void mutuallyDependentModsKeepTheirOrder() throws Exception {
        GraphTS<String> g = graph("first", "second");
        g.addEdge(0, 1);
        g.addEdge(1, 0);
        g.tsortStable();
        assertEquals("first", g.sortedArray.get(0),
                "a mutually dependent pair must not be reordered, got " + g.sortedArray);
    }

    /** A circular declaration must be survivable, not send the loader into recursion. */
    @Test
    public void aCircularDeclarationDoesNotRunAway() throws Exception {
        GraphTS<String> g = graph("a", "b", "c");
        g.addEdge(0, 1);
        g.addEdge(1, 0);   // a and b declare each other
        g.addEdge(1, 2);
        assertTimeoutPreemptively(java.time.Duration.ofSeconds(5), () -> {
            try {
                g.tsortStable();
            } catch (StackOverflowError e) {
                fail("a circular declaration must not recurse without bound");
            }
        });
        assertEquals(3, g.sortedArray.size(), "every mod must still be present");
    }

    /** A dependency declared on the most recently added mod still takes effect. */
    @Test
    public void anEdgeIntoTheNewestModTakesEffect() throws Exception {
        GraphTS<String> g = graph("first", "second", "newest");
        g.addEdge(2, 0);   // newest -> first: first depends on newest
        g.tsortStable();
        List<String> order = g.sortedArray;
        assertTrue(order.indexOf("newest") < order.indexOf("first"),
                "a dependency on the newest mod must still order it first, got " + order);
    }

    /** Depending on a mod is not the same as being depended on by it. */
    @Test
    public void theRelationIsNotSymmetric() throws Exception {
        GraphTS<String> g = graph("needsNothing", "needsTheOther");
        g.addEdge(0, 1);   // needsNothing -> needsTheOther
        g.tsortStable();
        assertEquals("needsNothing", g.sortedArray.get(0),
                "only the declared direction may reorder, got " + g.sortedArray);
    }
}
