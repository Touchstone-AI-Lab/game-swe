package com.example.recipesmith;

/** The recipe types a {@code recipes.yml} entry can declare, with their cooking defaults. */
enum RecipeKind {
    SHAPED("shaped", 0),
    SHAPELESS("shapeless", 0),
    SMELTING("smelting", 200),
    SMOKING("smoking", 100),
    BLASTING("blasting", 100),
    CAMPFIRE("campfire", 600),
    STONECUTTING("stonecutting", 0);

    private final String configName;
    private final int defaultCookingTime;

    RecipeKind(String configName, int defaultCookingTime) {
        this.configName = configName;
        this.defaultCookingTime = defaultCookingTime;
    }

    /** The name used in the file and in replies. */
    String configName() {
        return configName;
    }

    boolean isCooking() {
        return defaultCookingTime > 0;
    }

    int defaultCookingTime() {
        return defaultCookingTime;
    }

    /** Looks a type up by its exact configuration name; {@code null} when there is none. */
    static RecipeKind fromConfigName(String name) {
        for (RecipeKind kind : values()) {
            if (kind.configName.equals(name)) {
                return kind;
            }
        }
        return null;
    }
}
