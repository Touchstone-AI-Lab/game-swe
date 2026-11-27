package com.example.towncrier;

import java.util.List;

/** A group as read from {@code announcements.yml} after it passed validation. */
record GroupDefinition(
        String name,
        boolean enabled,
        long intervalSeconds,
        GroupOrder order,
        String permission,
        List<String> messages) {

    GroupDefinition {
        messages = List.copyOf(messages);
    }
}
