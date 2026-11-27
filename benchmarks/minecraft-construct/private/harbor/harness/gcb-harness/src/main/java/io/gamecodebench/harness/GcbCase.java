package io.gamecodebench.harness;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Marks a public instance method of a {@link GcbSuite} as a case.
 * Signature {@code ()} runs synchronously in one tick; {@code (GcbScript)} builds a ticked script.
 */
@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.METHOD)
public @interface GcbCase {

    /** Exact case name as frozen in the catalog. */
    String value();

    /** Run order: ascending order, then name. */
    int order() default 0;

    /** Tick timeout for a ticked case. */
    int ticks() default 600;
}
