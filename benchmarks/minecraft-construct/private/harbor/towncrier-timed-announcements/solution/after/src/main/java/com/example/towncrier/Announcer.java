package com.example.towncrier;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.regex.Pattern;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.minimessage.MiniMessage;
import org.bukkit.Bukkit;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

/** Loads the groups from announcements.yml, runs their timers and renders announcements. */
public final class Announcer {

    private static final Pattern NAME = Pattern.compile("^[a-z0-9_-]{1,32}$");

    private final TownCrierPlugin plugin;
    private final File file;
    private final Map<String, Group> groups = new TreeMap<>();
    private String prefix = "";

    public Announcer(TownCrierPlugin plugin) {
        this.plugin = plugin;
        this.file = new File(plugin.getDataFolder(), "announcements.yml");
    }

    /** The outcome of a load: counts and the reasons of the invalid groups, in file order. */
    public record LoadReport(int valid, int disabled, List<String> skipped) {
    }

    public LoadReport load() {
        stop();
        groups.clear();
        YamlConfiguration yaml = YamlConfiguration.loadConfiguration(file);
        prefix = yaml.getString("prefix", "");
        List<String> skipped = new ArrayList<>();
        int disabled = 0;
        ConfigurationSection section = yaml.getConfigurationSection("groups");
        if (section != null) {
            for (String name : section.getKeys(false)) {
                ConfigurationSection group = section.getConfigurationSection(name);
                String reason = validate(name, group);
                if (reason != null) {
                    skipped.add("Skipped " + name + ": " + reason + ".");
                    continue;
                }
                boolean enabled = group.getBoolean("enabled", true);
                if (!enabled) {
                    disabled++;
                }
                groups.put(name, new Group(name, enabled, group.getInt("interval"),
                    "shuffle".equals(group.getString("order", "sequential")), group.getString("permission", ""),
                    group.getStringList("messages")));
            }
        }
        for (Group group : groups.values()) {
            start(group);
        }
        return new LoadReport(groups.size(), disabled, skipped);
    }

    private static String validate(String name, ConfigurationSection group) {
        if (!NAME.matcher(name).matches()) {
            return "invalid name";
        }
        if (group == null || !group.isInt("interval") || group.getInt("interval") < 1) {
            return "interval must be a whole number of at least 1";
        }
        String order = group.getString("order", "sequential");
        if (!"sequential".equals(order) && !"shuffle".equals(order)) {
            return "order must be sequential or shuffle";
        }
        if (group.getStringList("messages").isEmpty()) {
            return "no messages";
        }
        return null;
    }

    public void stop() {
        for (Group group : groups.values()) {
            group.cancel();
        }
    }

    /** (Re)starts the group's timer when it is enabled and not paused. */
    public void start(Group group) {
        group.cancel();
        if (!group.enabled() || group.paused()) {
            return;
        }
        long period = group.interval() * 20L;
        long delay = group.remainingTicks() > 0 ? group.remainingTicks() : period;
        group.task(Bukkit.getScheduler().runTaskTimer(plugin, () -> {
            group.timerFired();
            announce(group);
        }, delay, period), delay);
    }

    public Group group(String name) {
        return groups.get(name);
    }

    public Collection<Group> groups() {
        return groups.values();
    }

    /** Broadcasts the group's next message; returns its 1-based index. */
    public int announce(Group group) {
        int index = group.next();
        Bukkit.broadcast(render(group, index), group.permission());
        return index + 1;
    }

    public Component render(Group group, int index) {
        String text = prefix + group.messages().get(index);
        text = text.replace("{group}", group.name())
            .replace("{index}", String.valueOf(index + 1))
            .replace("{count}", String.valueOf(group.messages().size()))
            .replace("{online}", String.valueOf(Bukkit.getOnlinePlayers().size()))
            .replace("{max}", String.valueOf(Bukkit.getMaxPlayers()));
        return MiniMessage.miniMessage().deserialize(text);
    }

    /** Writes the group's messages and interval back into announcements.yml, keeping everything else. */
    public void save(Group group) throws IOException {
        YamlConfiguration yaml = YamlConfiguration.loadConfiguration(file);
        yaml.set("groups." + group.name() + ".messages", new ArrayList<>(group.messages()));
        yaml.set("groups." + group.name() + ".interval", group.interval());
        yaml.save(file);
    }
}
