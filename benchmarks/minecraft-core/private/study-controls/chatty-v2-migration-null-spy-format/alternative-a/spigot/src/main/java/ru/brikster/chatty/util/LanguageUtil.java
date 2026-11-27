package ru.brikster.chatty.util;

import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

import java.util.List;
import java.util.Locale;

/**
 * Resolves the {@code language} setting to one of the bundled plugin languages.
 *
 * <p>Besides the canonical tags ({@code ru-RU}, {@code zh-CN}, ...) it accepts
 * the spellings Chatty 2 used for {@code general.locale} ({@code ru},
 * {@code zh_CN}, ...) and bare language codes, ignoring case and treating
 * {@code _} like {@code -}.
 */
public final class LanguageUtil {

    public static final String DEFAULT_LANGUAGE = "en-US";

    /** Supported language tags, in their canonical spelling. */
    public static final List<String> SUPPORTED_LANGUAGES =
            List.of(DEFAULT_LANGUAGE, "ru-RU", "de-DE", "es-ES", "zh-CN");

    private LanguageUtil() {
    }

    /**
     * Returns the canonical supported language tag matching {@code value},
     * or {@code null} when it matches none of them.
     */
    public static @Nullable String resolve(@Nullable String value) {
        if (value == null) {
            return null;
        }
        String normalized = value.trim().replace('_', '-');
        if (normalized.isEmpty()) {
            return null;
        }

        for (String language : SUPPORTED_LANGUAGES) {
            if (language.equalsIgnoreCase(normalized)) {
                return language;
            }
        }

        String code = normalized.toLowerCase(Locale.ROOT);
        for (String language : SUPPORTED_LANGUAGES) {
            if (languageCode(language).equals(code)) {
                return language;
            }
        }

        return null;
    }

    private static @NotNull String languageCode(@NotNull String language) {
        int separator = language.indexOf('-');
        String code = separator < 0 ? language : language.substring(0, separator);
        return code.toLowerCase(Locale.ROOT);
    }

}
