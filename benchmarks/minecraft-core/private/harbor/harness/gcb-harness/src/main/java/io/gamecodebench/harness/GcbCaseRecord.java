package io.gamecodebench.harness;

import java.lang.reflect.Method;

/** A registered case: the annotated method bound to its suite instance. */
record GcbCaseRecord(String name, int order, int ticks, GcbSuite suite, Method method) {

    boolean synchronous() {
        return method.getParameterCount() == 0;
    }
}
