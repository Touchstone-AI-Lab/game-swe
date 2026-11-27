package gcb;

/** Stands in for base-game methods a mod wants to short-circuit. */
public class EarlyReturnTarget {
    public static java.util.List<String> trace = new java.util.ArrayList<>();

    public static int amount(int x) {
        trace.add("body");
        return x * 10;
    }

    public static char grade(int x) {
        trace.add("gradeBody");
        return 'F';
    }

    public static void record(int x) {
        trace.add("recorded:" + x);
    }
}
