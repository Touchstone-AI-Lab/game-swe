package io.gamecodebench.harness;

import java.lang.reflect.InvocationTargetException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Drives registered cases in order, one per time, on the main thread. Each {@link #tick()}
 * executes at most one script step; a synchronous case completes within a single tick.
 */
final class SuiteRunner {

    private final List<GcbCaseRecord> cases;
    private final List<CaseResult> results = new ArrayList<>();
    private int index;
    private GcbScript script;
    private int consumed;

    SuiteRunner(List<GcbCaseRecord> cases) {
        this.cases = List.copyOf(cases);
    }

    boolean finished() {
        return index >= cases.size();
    }

    List<CaseResult> results() {
        return Collections.unmodifiableList(results);
    }

    void tick() {
        if (finished()) {
            return;
        }
        GcbCaseRecord current = cases.get(index);
        if (current.synchronous()) {
            runSynchronous(current);
            return;
        }
        if (script == null) {
            consumed = 1;
            script = new GcbScript();
            if (!invoke(current, script)) {
                return;
            }
        } else {
            consumed++;
        }
        try {
            if (script.advance()) {
                finish(CaseResult.pass(current.name(), consumed));
            } else if (consumed >= current.ticks()) {
                finish(CaseResult.fail(current.name(),
                    "hung: exceeded " + current.ticks() + " ticks (" + script.pendingDescription() + ")", consumed));
            }
        } catch (Throwable thrown) {
            finish(CaseResult.fail(current.name(), CaseResult.describe(thrown), consumed));
        }
    }

    private void runSynchronous(GcbCaseRecord current) {
        consumed = 1;
        if (invoke(current)) {
            finish(CaseResult.pass(current.name(), consumed));
        }
    }

    /** Invokes the case method; on failure records the result and returns false. */
    private boolean invoke(GcbCaseRecord current, Object... args) {
        try {
            current.method().invoke(current.suite(), args);
            return true;
        } catch (InvocationTargetException wrapped) {
            finish(CaseResult.fail(current.name(), CaseResult.describe(wrapped.getCause()), consumed));
        } catch (Throwable thrown) {
            finish(CaseResult.fail(current.name(), CaseResult.describe(thrown), consumed));
        }
        return false;
    }

    private void finish(CaseResult result) {
        results.add(result);
        script = null;
        consumed = 0;
        index++;
    }
}
