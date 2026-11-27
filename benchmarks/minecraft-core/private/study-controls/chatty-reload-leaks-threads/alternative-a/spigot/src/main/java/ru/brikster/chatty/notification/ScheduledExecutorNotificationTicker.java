package ru.brikster.chatty.notification;

import javax.inject.Singleton;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

/**
 * Ticks the registered notifications once per second on its own thread.
 * <p>
 * Every configuration (plugin enable or {@code /chatty reload}) builds a new
 * ticker. {@link #cancelTicking()} stops a ticker for good: it shuts its
 * executor down, so the ticking thread terminates instead of idling until the
 * server stops.
 */
@Singleton
public final class ScheduledExecutorNotificationTicker implements NotificationTicker {

    private static final String THREAD_NAME = "Chatty Notification Ticker";
    private static final long TERMINATION_TIMEOUT_MILLIS = 1000L;

    // The executor creates its thread lazily, when the first tick is scheduled.
    private final ScheduledExecutorService executor =
            Executors.newSingleThreadScheduledExecutor(ScheduledExecutorNotificationTicker::newTickerThread);
    private ScheduledFuture<?> future;

    private final List<Notification> notificationList = new ArrayList<>();

    @Override
    public void addNotification(Notification notification) {
        notificationList.add(notification);
    }

    @Override
    public void clearNotifications() {
        notificationList.clear();
    }

    @Override
    public synchronized void startTicking() {
        if (executor.isShutdown()) {
            throw new IllegalStateException("This notification ticker was cancelled and cannot tick again");
        }
        if (future != null) {
            // Already ticking: never schedule the notifications twice.
            return;
        }
        this.future = executor.scheduleAtFixedRate(this::tickNotifications, 1, 1, TimeUnit.SECONDS);
    }

    private void tickNotifications() {
        try {
            for (Notification notification : notificationList) {
                if (executor.isShutdown()) {
                    // Cancelled while this tick was running: stop advancing notifications.
                    return;
                }
                notification.tick();
            }
        } catch (Throwable t) {
            //noinspection CallToPrintStackTrace
            t.printStackTrace();
        }
    }

    /**
     * Stops ticking for good and releases the ticking thread. Safe to call on a
     * ticker that never started ticking, and safe to call more than once.
     */
    @Override
    public void cancelTicking() {
        synchronized (this) {
            if (future != null) {
                future.cancel(false);
            }
            executor.shutdown();
        }
        awaitTermination();
    }

    private void awaitTermination() {
        try {
            // Lets a tick that is still running finish, so no notification
            // advances once cancelTicking() has returned.
            if (!executor.awaitTermination(TERMINATION_TIMEOUT_MILLIS, TimeUnit.MILLISECONDS)) {
                executor.shutdownNow();
            }
        } catch (InterruptedException e) {
            executor.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }

    private static Thread newTickerThread(Runnable task) {
        Thread thread = new Thread(task, THREAD_NAME);
        thread.setDaemon(true);
        return thread;
    }

}
