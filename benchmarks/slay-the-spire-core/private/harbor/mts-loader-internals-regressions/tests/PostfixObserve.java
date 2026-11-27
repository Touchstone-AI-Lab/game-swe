package gcb;

/**
 * A postfix that observes the result and hands it back unchanged.
 *
 * The return type matches the parameter type deliberately: that is how this engine
 * decides a postfix wants the result rather than the original argument.
 */
public class PostfixObserve {
    public static int Postfix(int __result) {
        PostfixTarget.trace.add("postfix:" + __result);
        return __result;
    }
}
