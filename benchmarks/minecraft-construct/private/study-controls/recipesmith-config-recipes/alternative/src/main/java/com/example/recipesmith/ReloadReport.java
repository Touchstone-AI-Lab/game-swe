package com.example.recipesmith;

import java.util.ArrayList;
import java.util.List;

/** The outcome of a reload, rendered as the reply lines of {@code /recipes reload}. */
record ReloadReport(int loaded, List<Skip> skipped, int disabled, List<String> unknownVanilla) {

    /** A recipe that failed validation, with the first failing reason. */
    record Skip(String id, String reason) {
    }

    ReloadReport {
        skipped = List.copyOf(skipped);
        unknownVanilla = List.copyOf(unknownVanilla);
    }

    List<String> lines() {
        List<String> lines = new ArrayList<>();
        lines.add("Loaded " + loaded + " recipes, skipped " + skipped.size() + ", disabled " + disabled
                + " vanilla recipes.");
        for (Skip skip : skipped) {
            lines.add("Skipped " + skip.id() + ": " + skip.reason() + ".");
        }
        for (String key : unknownVanilla) {
            lines.add("Unknown vanilla recipe: " + key);
        }
        return lines;
    }
}
