package gcb;

/** Stands in for a base-game method a mod wants to patch. */
public class Target {
    public static int lastSeen = -1;
    public static void take(int x) { lastSeen = x; }
}
