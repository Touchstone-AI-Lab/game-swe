package gcb;

/** Stands in for a base-game method a mod decorates with a postfix patch. */
public class PostfixTarget {
    public static java.util.List<String> trace = new java.util.ArrayList<>();

    public static int doubled(int x) {
        trace.add("body");
        return x * 2;
    }
}
