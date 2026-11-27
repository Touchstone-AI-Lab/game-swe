package com.example.towncrier;

import java.util.List;

/**
 * The outcome of reading {@code announcements.yml}: the prefix, the valid groups and the
 * invalid ones, both in file order.
 */
record LoadResult(String prefix, List<GroupDefinition> groups, List<Skipped> skipped) {

    /** An invalid group and the first validation check it failed. */
    record Skipped(String name, String reason) {
    }

    LoadResult {
        groups = List.copyOf(groups);
        skipped = List.copyOf(skipped);
    }

    long disabledCount() {
        return groups.stream().filter(group -> !group.enabled()).count();
    }
}
