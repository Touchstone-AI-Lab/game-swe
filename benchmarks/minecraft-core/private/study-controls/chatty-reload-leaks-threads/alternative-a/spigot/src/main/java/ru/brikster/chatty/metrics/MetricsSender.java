package ru.brikster.chatty.metrics;

import org.bstats.bukkit.Metrics;
import org.bstats.charts.SimplePie;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;
import ru.brikster.chatty.config.file.*;
import ru.brikster.chatty.util.PaperUtil;

import javax.inject.Inject;
import javax.inject.Singleton;

@Singleton
public class MetricsSender {

    @Inject private Plugin plugin;
    @Inject private SettingsConfig settingsConfig;
    @Inject private PmConfig pmConfig;
    @Inject private NotificationsConfig notificationsConfig;
    @Inject private ModerationConfig moderationConfig;
    @Inject private VanillaConfig vanillaConfig;

    // bStats instance started by run(); it owns a "bStats-Metrics" thread until shut down.
    private Metrics metrics;

    public void run() {
        shutdown();
        if (settingsConfig.isSendMetrics()) {
            if (PaperUtil.isFolia()) {
                plugin.getLogger().info("Skipping bStats metrics: the bundled version"
                        + " uses the Bukkit scheduler, which Folia does not provide.");
                return;
            }
            Metrics metrics = new Metrics((JavaPlugin) plugin, 3466);
            this.metrics = metrics;
            metrics.addCustomChart(new SimplePie("language",
                    () -> settingsConfig.getLanguage()));

            metrics.addCustomChart(new SimplePie("private_messaging",
                    () -> String.valueOf(pmConfig.isEnable())));

            metrics.addCustomChart(new SimplePie("spy",
                    () -> String.valueOf(pmConfig.getSpy().isEnable())));

            metrics.addCustomChart(new SimplePie("chat_notifications",
                    () -> String.valueOf(notificationsConfig.getChat().isEnable())));

            metrics.addCustomChart(new SimplePie("actionbar_notifications",
                    () -> String.valueOf(notificationsConfig.getActionbar().isEnable())));

            metrics.addCustomChart(new SimplePie("caps_moderation_method",
                    () -> String.valueOf(moderationConfig.getCaps().isEnable())));

            metrics.addCustomChart(new SimplePie("adv_moderation_method",
                    () -> String.valueOf(moderationConfig.getAdvertisement().isEnable())));

            metrics.addCustomChart(new SimplePie("swear_moderation_method",
                    () -> String.valueOf(moderationConfig.getSwear().isEnable())));

            metrics.addCustomChart(new SimplePie("miscellaneous_join_msg",
                    () -> String.valueOf(vanillaConfig.getJoin().isEnable())));

            metrics.addCustomChart(new SimplePie("miscellaneous_quit_msg",
                    () -> String.valueOf(vanillaConfig.getQuit().isEnable())));

            metrics.addCustomChart(new SimplePie("miscellaneous_death_msg",
                    () -> String.valueOf(vanillaConfig.getDeath().isEnable())));

            metrics.addCustomChart(new SimplePie("debug",
                    () -> String.valueOf(settingsConfig.isDebug())));
        }
    }

    /**
     * Stops the bStats instance started by {@link #run()}, if any, so that its
     * {@code bStats-Metrics} thread terminates. Safe to call more than once.
     */
    public void shutdown() {
        Metrics current = this.metrics;
        this.metrics = null;
        if (current != null) {
            current.shutdown();
        }
    }

}
