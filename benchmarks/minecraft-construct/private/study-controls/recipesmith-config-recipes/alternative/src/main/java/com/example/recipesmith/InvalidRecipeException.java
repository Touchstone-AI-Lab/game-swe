package com.example.recipesmith;

/** Thrown when a recipe entry fails validation; the message is the reason shown to the sender. */
final class InvalidRecipeException extends Exception {
    private static final long serialVersionUID = 1L;

    InvalidRecipeException(String reason) {
        super(reason, null, false, false);
    }

    String reason() {
        return getMessage();
    }
}
