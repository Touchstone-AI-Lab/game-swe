package com.example.towncrier;

import java.util.Optional;

/** The order in which a group walks through its messages. */
enum GroupOrder {
    SEQUENTIAL("sequential"),
    SHUFFLE("shuffle");

    private final String key;

    GroupOrder(String key) {
        this.key = key;
    }

    /** The exact spelling used in {@code announcements.yml} and in {@code /crier list}. */
    String key() {
        return key;
    }

    /** Resolves the exact file spelling; anything else is not an order. */
    static Optional<GroupOrder> fromKey(String key) {
        for (GroupOrder order : values()) {
            if (order.key.equals(key)) {
                return Optional.of(order);
            }
        }
        return Optional.empty();
    }
}
