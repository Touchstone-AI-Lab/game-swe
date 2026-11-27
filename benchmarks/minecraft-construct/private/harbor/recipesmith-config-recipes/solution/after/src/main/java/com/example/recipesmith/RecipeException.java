package com.example.recipesmith;

/** A recipe entry that cannot be registered, or a rejected command; the message is the reason. */
public final class RecipeException extends Exception {

    public RecipeException(String message) {
        super(message);
    }
}
