package io.gamecodebench.harness;

/** A body that may throw; used by script steps and by {@link GcbAssert#throwsType}. */
@FunctionalInterface
public interface GcbRunnable {
    void run() throws Exception;
}
