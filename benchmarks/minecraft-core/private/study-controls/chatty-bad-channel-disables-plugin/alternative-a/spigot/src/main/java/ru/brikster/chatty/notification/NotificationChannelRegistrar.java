package ru.brikster.chatty.notification;

import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Registers the channels of one section of {@code notifications.yml}, one at a
 * time, so that a channel which cannot be used is skipped and reported instead
 * of aborting the whole configuration load (and with it the plugin).
 */
public final class NotificationChannelRegistrar {

    public static final String NOTIFICATIONS_FILE = "notifications.yml";

    private NotificationChannelRegistrar() {
    }

    /**
     * Creates a notification for one configured channel.
     *
     * @param <C> the channel configuration type
     */
    @FunctionalInterface
    public interface ChannelFactory<C> {

        /**
         * @return the notification to register, or {@code null} to skip the
         * channel silently (the factory has already reported why)
         * @throws InvalidChannelException if the channel settings cannot be used
         */
        @Nullable Notification create(@NotNull String channelId, @NotNull C channelConfig);

    }

    /**
     * Thrown by a {@link ChannelFactory} when a channel's settings cannot be used.
     * The message explains why, in words meant for the server owner.
     */
    public static final class InvalidChannelException extends RuntimeException {

        public InvalidChannelException(String reason) {
            super(reason);
        }

    }

    /**
     * Registers every usable channel of {@code channels} into {@code ticker}.
     * Each channel that cannot be used is left out and logged at
     * {@link Level#WARNING} with its id and the reason; the remaining channels,
     * including those listed after it, are registered as usual.
     *
     * @param section the section name in {@code notifications.yml}, e.g. {@code actionbar}
     */
    public static <C> void register(@NotNull NotificationTicker ticker,
                                    @NotNull Logger logger,
                                    @NotNull String section,
                                    @Nullable Map<String, C> channels,
                                    @NotNull ChannelFactory<C> factory) {
        if (channels == null) {
            logger.warning("The \"" + section + "\" section of " + NOTIFICATIONS_FILE
                    + " has no \"lists\" of channels, so no " + section + " notifications were registered.");
            return;
        }

        channels.forEach((channelId, channelConfig) -> {
            if (channelConfig == null) {
                logger.warning(skippedMessage(section, channelId, "it has no settings"));
                return;
            }

            Notification notification;
            try {
                notification = factory.create(channelId, channelConfig);
            } catch (InvalidChannelException e) {
                logger.warning(skippedMessage(section, channelId, e.getMessage()));
                return;
            } catch (RuntimeException e) {
                String reason = e.getMessage() == null || e.getMessage().isBlank()
                        ? e.getClass().getSimpleName()
                        : e.getMessage();
                logger.log(Level.WARNING, skippedMessage(section, channelId,
                        "its settings cannot be used (" + reason + ")"), e);
                return;
            }

            if (notification != null) {
                ticker.addNotification(notification);
            }
        });
    }

    private static String skippedMessage(String section, String channelId, String reason) {
        return "Skipped the " + section + " notification channel \"" + channelId + "\" in "
                + NOTIFICATIONS_FILE + ": " + reason + ". The channel was not registered;"
                + " fix it and run /chatty reload.";
    }

}
