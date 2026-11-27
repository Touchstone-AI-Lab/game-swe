package io.gamecodebench.harness;

/** The {@code gcb.*} system properties set by verify.py / bootstrap.sh. */
record HarnessSettings(String mode, String nonce, String candidate, int maxTicks, int settleTicks) {

    static final String MODE_BOOTSTRAP = "bootstrap";
    static final String MODE_RUN_SUITE = "run-suite";

    static HarnessSettings fromSystemProperties() {
        return new HarnessSettings(
            System.getProperty("gcb.mode", MODE_RUN_SUITE).trim(),
            System.getProperty("gcb.nonce", ""),
            System.getProperty("gcb.candidate", ""),
            Integer.getInteger("gcb.maxTicks", 6000),
            Integer.getInteger("gcb.settleTicks", 20));
    }

    boolean bootstrap() {
        return MODE_BOOTSTRAP.equals(mode);
    }
}
