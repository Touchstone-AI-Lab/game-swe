package com.booksaw.betterTeams.commands.team;

import com.booksaw.betterTeams.*;
import com.booksaw.betterTeams.commands.ParentCommand;
import com.booksaw.betterTeams.commands.SubCommand;
import com.booksaw.betterTeams.message.HelpMessage;
import com.booksaw.betterTeams.message.MessageManager;
import com.booksaw.betterTeams.team.SetTeamComponent;
import com.booksaw.betterTeams.text.Formatter;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.TextReplacementConfig;
import net.kyori.adventure.text.minimessage.MiniMessage;
import org.bukkit.ChatColor;
import org.bukkit.OfflinePlayer;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.jetbrains.annotations.Nullable;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.function.Function;

/**
 * This class handles the command /team info [team/player]
 *
 * @author booksaw
 */
public class InfoCommand extends SubCommand {

	/**
	 * The placeholder of the {@code info.description} message that is replaced
	 * by the team description.
	 */
	private static final String DESCRIPTION_PLACEHOLDER = "{0}";

	private final ParentCommand parentCommand;

	public InfoCommand(ParentCommand parentCommand) {
		this.parentCommand = parentCommand;
	}

	/**
	 * Builds the lines of the info screen as unparsed message strings.
	 * <p>
	 * The team description is player-controlled input, so it is embedded in a
	 * form in which only its colour, decoration and reset formatting is
	 * interpreted when the line is parsed; every other tag (click, hover,
	 * insertion, translatable, ...) is kept as literal text. {@code /team info}
	 * itself displays {@link #getInfoComponents(Team)}.
	 *
	 * @param team the team to describe
	 * @return the info lines, {@code null} or empty for lines that are not shown
	 */
	public static List<@Nullable String> getInfoMessages(Team team) {
		return buildInfo(team, Function.identity(), InfoCommand::getDescriptionMessage);
	}

	/**
	 * Builds the lines of the info screen as components, without the plugin
	 * prefix.
	 * <p>
	 * The description line is built from the {@code info.description} template
	 * with the description inserted as a separately parsed component, so the
	 * description can only carry colour, decoration and reset formatting and can
	 * never add click, hover or insertion events or non-text content.
	 *
	 * @param team the team to describe
	 * @return the info lines, {@code null} for lines that are not shown
	 */
	public static List<@Nullable Component> getInfoComponents(Team team) {
		return buildInfo(team, InfoCommand::toComponent, InfoCommand::getDescriptionComponent);
	}

	private static <T> List<@Nullable T> buildInfo(Team team, Function<@Nullable String, @Nullable T> line,
			Function<String, @Nullable T> descriptionLine) {
		List<@Nullable T> infoMessages = new ArrayList<>();

		infoMessages.add(line.apply(MessageManager.getMessage("info.name", team.getDisplayName())));
		String description = team.getDescription();
		if (description != null && !description.isEmpty()) {
			infoMessages.add(descriptionLine.apply(description));
		}

		infoMessages.add(line.apply(MessageManager.getMessage("info.open", team.isOpen())));
		infoMessages.add(line.apply(MessageManager.getMessage("info.score", team.getScore())));
		infoMessages.add(line.apply(MessageManager.getMessage("info.money", team.getBalance())));
		infoMessages.add(line.apply(MessageManager.getMessage("info.level", team.getLevel())));

		int currentMembers = team.getMembers().size();
		int maxMembers = team.getTeamLimit();
		int currentWarps = team.getWarps().size();
		int maxWarps = team.getMaxWarps();

		infoMessages.add(line.apply(MessageManager.getMessage("info.limits",
				currentMembers, maxMembers, currentWarps, maxWarps)));

		infoMessages.add(line.apply(MessageManager.getMessage("info.tag", team.getTag())));

		if (Main.plugin.getConfig().getBoolean("anchor.enable")) {
			infoMessages.add(line.apply(MessageManager.getMessage("info.anchor", team.isAnchored())));
		}

		infoMessages.add(line.apply(getAlliesMessage(team)));
		infoMessages.add(line.apply(getPlayerList(team, PlayerRank.OWNER)));
		infoMessages.add(line.apply(getPlayerList(team, PlayerRank.ADMIN)));
		infoMessages.add(line.apply(getPlayerList(team, PlayerRank.DEFAULT)));

		return infoMessages;
	}

	/**
	 * Parses a plugin message line exactly as
	 * {@link MessageManager#sendFullMessage(CommandSender, String, boolean)} does.
	 */
	private static @Nullable Component toComponent(@Nullable String message) {
		if (message == null || message.isEmpty()) {
			return null;
		}
		return Formatter.absolute().process(message);
	}

	/**
	 * Parses a team description. {@link Formatter#legacy()} only resolves colour,
	 * decoration, gradient, rainbow and reset tags (and legacy {@code &} codes);
	 * every other tag is left as the literal text that was typed.
	 */
	private static Component parseDescription(String description) {
		return Formatter.legacy().process(description);
	}

	/**
	 * Builds the description line: the {@code info.description} template is
	 * parsed on its own and the parsed description is inserted in place of its
	 * placeholder, inheriting the template's formatting at that position (the
	 * value colour). The description text is never parsed together with the
	 * template, so it cannot introduce any tag the template would interpret.
	 */
	private static @Nullable Component getDescriptionComponent(String description) {
		Component template = toComponent(MessageManager.getMessage("info.description"));
		if (template == null) {
			return null;
		}

		Component parsedDescription = parseDescription(description);
		return template.replaceText(TextReplacementConfig.builder()
				.matchLiteral(DESCRIPTION_PLACEHOLDER)
				.replacement(matched -> matched.content("").append(parsedDescription))
				.build());
	}

	/**
	 * Builds the description line as an unparsed message string, with the
	 * description re-serialized so that all of its text is escaped and only its
	 * colour, decoration and reset formatting remains as tags.
	 */
	private static String getDescriptionMessage(String description) {
		String template = MessageManager.getMessage("info.description");
		if (template.isEmpty()) {
			return template;
		}
		String safeDescription = MiniMessage.miniMessage().serialize(parseDescription(description));
		return template.replace(DESCRIPTION_PLACEHOLDER, safeDescription);
	}

	private static String getSetComponentMessage(SetTeamComponent<UUID> teams, final String referenceMessage) {
		StringBuilder tmp = new StringBuilder();
		for (UUID uuid : teams.get()) {
			Team ally = Team.getTeam(uuid);

			if (ally == null) {
				Main.plugin.getLogger().warning("Unable to locate team with UUID: " + uuid);
				continue;
			}

			tmp.append(ally.getDisplayName()).append(ChatColor.WHITE).append(", ");
		}

		if (tmp.length() > 2) {
			return MessageManager.getMessage(referenceMessage, tmp.substring(0, tmp.length() - 2));
		}

		return null;
	}

	private static String getAlliesMessage(Team team) {
		return getSetComponentMessage(team.getAllies(), "info.ally");
	}

	private static String getPlayerList(Team team, PlayerRank rank) {
		List<TeamPlayer> users = team.getRank(rank);

		if (!users.isEmpty()) {
			String space = MessageManager.getMessage("info.playerListSpace");
			List<String> playerList = new ArrayList<>();
			for (TeamPlayer player : users) {
				OfflinePlayer offplayer = player.getPlayer();
				playerList.add(MessageManager.getMessage(offplayer, "info." + ((offplayer.isOnline()
								&& player.getOnlinePlayer().map(
								p -> !Utils.isVanished(p)).orElse(false)) ? "onlinePlayer" : "offlinePlayer"),
						player.getPlayerPrefix() + offplayer.getName()));
			}

			return MessageManager.getMessage("info." + rank.toString().toLowerCase(), String.join(space, playerList));
		}

		return null;
	}

	@Override
	public CommandResponse onCommand(CommandSender sender, String label, String[] args) {
		if (args.length == 0) {
			if (!(sender instanceof Player)) {
				return new CommandResponse(new HelpMessage(this, label, parentCommand));
			}
			Team team = Team.getTeam((Player) sender);
			if (team == null) {
				return new CommandResponse(new HelpMessage(this, label, parentCommand));
			}
			displayTeamInfo(sender, team);
			return new CommandResponse(true);
		}

		// player or team has been entered
		// trying by team name
		Team team = Team.getTeam(args[0]);

		if (team != null) {
			displayTeamInfo(sender, team);
			return new CommandResponse(true);
		}

		// trying by player name
		/*
		 * method is depreciated as it does not guarantee the expected player, in most
		 * use cases this will work and it will be down to the user if it does not due
		 * to name changes This method is appropriate to use in this use case (so users
		 * can view offline users teams by name not just by team name)
		 */
		OfflinePlayer player = Utils.getOfflinePlayer(args[0]);

		if (player != null) {
			team = Team.getTeam(player);
			if (team != null) {
				displayTeamInfo(sender, team);
				return null;
			}
		}
		return new CommandResponse("info.needTeam");

	}

	private void displayTeamInfo(CommandSender sender, Team team) {
		List<@Nullable Component> toDisplay = getInfoComponents(team);

		for (Component line : toDisplay) {
			if (line == null) {
				continue;
			}
			MessageManager.sendFullMessage(sender, line, true);
		}
	}

	@Override
	public String getCommand() {
		return "info";
	}

	@Override
	public int getMinimumArguments() {
		return 0;
	}

	@Override
	public String getNode() {
		return "info";
	}

	@Override
	public String getHelp() {
		return "View information about the specified player / team";
	}

	@Override
	public String getArguments() {
		return "[team/player]";
	}

	@Override
	public int getMaximumArguments() {
		return 2;
	}

	@Override
	public void onTabComplete(List<String> options, CommandSender sender, String label, String[] args) {

		addTeamStringList(options, (args.length == 0) ? "" : args[0]);
		addPlayerStringList(options, (args.length == 0) ? "" : args[0]);

	}

}
