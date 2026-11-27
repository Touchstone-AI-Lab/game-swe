package gcb;

/** A prefix that only observes: it never asks to answer on the method's behalf, so the
 *  early-return machinery is not involved at all. */
public class PlainPrefix {
    public static void Prefix(int x) {
        EarlyReturnTarget.trace.add("prefix:" + x);
    }
}
