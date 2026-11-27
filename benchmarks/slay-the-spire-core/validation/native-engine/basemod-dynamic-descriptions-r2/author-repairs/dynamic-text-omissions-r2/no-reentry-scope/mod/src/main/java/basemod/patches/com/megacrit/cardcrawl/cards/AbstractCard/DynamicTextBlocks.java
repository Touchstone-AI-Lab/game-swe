package basemod.patches.com.megacrit.cardcrawl.cards.AbstractCard;

import basemod.BaseMod;
import basemod.helpers.CardModifierManager;
import com.evacipated.cardcrawl.modthespire.lib.*;
import com.megacrit.cardcrawl.actions.GameActionManager;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.cards.CardGroup;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.screens.ExhaustPileViewScreen;
import com.megacrit.cardcrawl.screens.SingleCardViewPopup;
import javassist.CannotCompileException;
import javassist.CtBehavior;
import javassist.expr.ExprEditor;
import javassist.expr.MethodCall;
import org.apache.commons.lang3.StringUtils;
import org.apache.commons.lang3.math.NumberUtils;

import java.util.Arrays;
import java.util.HashMap;
import java.util.function.Function;
import java.util.regex.Pattern;

public class DynamicTextBlocks {
    private static final String REGEX = "\\{!.*?!\\|.*?}";
    private static final String DYNAMIC_KEY = "{@@}";
    private static final Pattern PATTERN = Pattern.compile(REGEX);
    private static final HashMap<String, Function<AbstractCard, Integer>> customChecks = new HashMap<>();

    public static void registerCustomCheck(String s, Function<AbstractCard, Integer> f) {
        if (s.charAt(0) != '!' && !s.endsWith("!")) {
            s = "!" + s + "!";
        }
        customChecks.put(s, f);
    }

    //Spire Field for fixing the Location var in ExhaustPileViewScreen thanks to the fact it returns a copy of the card that isn't actually in the Exhaust pile when you pull up the screen
    @SpirePatch(clz= AbstractCard.class, method=SpirePatch.CLASS)
    public static class ExhaustViewFixField {
        public static final SpireField<Boolean> exhaustViewCopy = new SpireField<>(() -> Boolean.FALSE);
    }

    //Spire Field for if dynamic text was found. This allows faster checking since we don't need to regex each time
    @SpirePatch(clz= AbstractCard.class, method=SpirePatch.CLASS)
    public static class DynamicTextField {
        public static final SpireField<Boolean> isDynamic = new SpireField<>(() -> Boolean.FALSE);
        public static final SpireField<String> varData = new SpireField<>(() -> "");
    }

    //Spire Field for if displayUpgrades was called
    @SpirePatch(clz= AbstractCard.class, method=SpirePatch.CLASS)
    public static class DisplayingUpgradesField {
        public static final SpireField<Boolean> displayingUpgrades = new SpireField<>(() -> Boolean.FALSE);
    }

    //When we render said card copy, set its field and initialize description
    @SpirePatch(clz = ExhaustPileViewScreen.class, method = "open")
    public static class FixExhaustText {
        @SpireInsertPatch(locator = Locator.class, localvars = "toAdd")
        public static void setField(ExhaustPileViewScreen __instance, AbstractCard toAdd) {
            if (DynamicTextField.isDynamic.get(toAdd)) {
                ExhaustViewFixField.exhaustViewCopy.set(toAdd, true);
            }
        }

        private static class Locator extends SpireInsertLocator {
            @Override
            public int[] Locate(CtBehavior ctMethodToPatch) throws Exception {
                Matcher finalMatcher = new Matcher.MethodCallMatcher(CardGroup.class, "addToBottom");
                return LineFinder.findInOrder(ctMethodToPatch, finalMatcher);
            }
        }
    }

    //Patch to take place in for the foreach loop. Takes place after card mod patch
    @SpirePatch(clz = AbstractCard.class, method = "initializeDescription")
    @SpirePatch(clz = AbstractCard.class, method = "initializeDescriptionCN")
    public static class ProcessDynamicText {
        @SpireInstrumentPatch
        public static ExprEditor patch() {
            return new ExprEditor() {
                @Override
                public void edit(MethodCall m) throws CannotCompileException {
                    if (m.getClassName().equals(String.class.getName()) && m.getMethodName().equals("split")) {
                        m.replace("{ $_ = " + basemod.patches.com.megacrit.cardcrawl.cards.AbstractCard.DynamicTextBlocks.class.getName()+".checkForUnwrapping(this, $proceed($$)); }");
                    }
                }
            };
        }
    }

    //Force an update at render time if the values have changed since we last checked
    @SpirePatch2(clz = AbstractCard.class, method = "renderDescription")
    @SpirePatch2(clz = AbstractCard.class, method = "renderDescriptionCN")
    public static class UpdateOnRender {
        @SpirePrefixPatch
        public static void onRender(AbstractCard __instance) {
            __instance.initializeDescription();
        }
    }

    //Force an update at render time if the values have changed since we last checked, SCV style
    @SpirePatch2(clz = SingleCardViewPopup.class, method = "renderDescription")
    @SpirePatch2(clz = SingleCardViewPopup.class, method = "renderDescriptionCN")
    public static class UpdateOnRenderSCV {
        @SpirePrefixPatch
        public static void onRender(SingleCardViewPopup __instance, AbstractCard ___card) {
            ___card.initializeDescription();
        }
    }

    public static String parseVarData(AbstractCard c) {
        StringBuilder sb = new StringBuilder();
        java.util.regex.Matcher m = PATTERN.matcher(c.rawDescription.replace(DYNAMIC_KEY,""));
        while (m.find()) {
            String key = m.group().substring(1, m.group().length()-1).split("\\|")[0];
            Integer var = getVarFromDynvarKey(c, key);
            sb.append(key).append(var != null ? var : "?");
        }
        return sb.toString();
    }

    public static String[] checkForUnwrapping(AbstractCard card, String[] splitText) {
        String text = String.join(" ", splitText);
        boolean opted = text.contains(DYNAMIC_KEY);
        DynamicTextField.isDynamic.set(card, opted);
        if (!opted) return splitText;
        return expandText(card, text.replace(DYNAMIC_KEY, "")).split(" ", -1);
    }


    private static boolean quoted(char ch) { return ch == '|' || ch == '{' || ch == '}' || ch == '\\'; }
    private static int closing(String text, int begin) {
        int depth = 0;
        for (int i = begin; i < text.length(); ++i) {
            char ch = text.charAt(i);
            if (ch == '\\' && i + 1 < text.length() && quoted(text.charAt(i + 1))) { ++i; continue; }
            if (ch == '{') ++depth;
            if (ch == '}') { --depth; if (depth == 0) return i; }
        }
        return -1;
    }
    private static java.util.List<String> segments(String text, char separator, boolean firstOnly) {
        java.util.List<String> result = new java.util.ArrayList<>();
        int depth = 0, begin = 0;
        for (int i = 0; i < text.length(); ++i) {
            char ch = text.charAt(i);
            if (ch == '\\' && i + 1 < text.length() && quoted(text.charAt(i + 1))) { ++i; continue; }
            if (ch == '{') ++depth;
            else if (ch == '}') --depth;
            else if (ch == separator && depth == 0) {
                result.add(text.substring(begin, i)); begin = i + 1;
                if (firstOnly) break;
            }
        }
        result.add(text.substring(begin));
        return result;
    }
    private static boolean matches(int value, String condition) {
        condition = condition.trim();
        if (condition.startsWith("&")) {
            String digits = condition.substring(1);
            return digits.matches("[0-9]+") && Long.toString(Math.abs((long) value)).endsWith(digits);
        }
        char operation = condition.isEmpty() ? '=' : condition.charAt(0);
        String operand = operation == '>' || operation == '<' || operation == '%' ? condition.substring(1) : condition;
        if (!operand.matches("[+-]?[0-9]+")) return false;
        final int number;
        try { number = Integer.parseInt(operand); } catch (NumberFormatException ignored) { return false; }
        if (operation == '>') return value > number;
        if (operation == '<') return value < number;
        if (operation == '%') return number != 0 && value % number == 0;
        return value == number;
    }
    private static class Values {
        final AbstractCard card;
        final java.util.Map<String, Integer> memo = new java.util.HashMap<>();
        Values(AbstractCard card) { this.card = card; }
        Integer read(String key) {
            if (!memo.containsKey(key)) memo.put(key, getVarFromDynvarKey(card, key));
            return memo.get(key);
        }
    }

    private interface Piece { String render(Values values); }
    private static final class Literal implements Piece {
        final String text;
        Literal(String text) { this.text = text; }
        public String render(Values values) { return text; }
    }
    private static final class Choice implements Piece {
        final String key;
        final java.util.List<String> conditions = new java.util.ArrayList<>();
        final java.util.List<java.util.List<Piece>> payloads = new java.util.ArrayList<>();
        Choice(String body) {
            java.util.List<String> parts = segments(body, '|', false);
            key = parts.get(0);
            for (int i = 1; i < parts.size(); ++i) {
                java.util.List<String> branch = segments(parts.get(i), '=', true);
                if (branch.size() == 2) { conditions.add(branch.get(0)); payloads.add(parse(branch.get(1))); }
            }
        }
        public String render(Values values) {
            Integer value = values.read(key);
            if (value == null) return "";
            int selected = -1, fallback = -1, copies = 1;
            for (int i = 0; i < conditions.size(); ++i) {
                String condition = conditions.get(i).trim();
                if (condition.equals("@")) { fallback = i; continue; }
                if (condition.equals("repeat")) { selected = i; copies = Math.max(0, value); continue; }
                for (String alternative : condition.split(",", -1)) {
                    if (matches(value, alternative)) { selected = i; copies = 1; break; }
                }
            }
            if (selected < 0) { selected = fallback; copies = 1; }
            if (selected < 0 || copies == 0) return "";
            String payload = renderPieces(payloads.get(selected), values);
            StringBuilder result = new StringBuilder();
            for (int i = 0; i < copies; ++i) result.append(payload);
            return result.toString();
        }
    }
    private static java.util.List<Piece> parse(String text) {
        java.util.List<Piece> pieces = new java.util.ArrayList<>();
        StringBuilder literal = new StringBuilder();
        for (int i = 0; i < text.length();) {
            char ch = text.charAt(i);
            if (ch == '\\' && i + 1 < text.length() && quoted(text.charAt(i + 1))) {
                literal.append(text.charAt(i + 1)); i += 2; continue;
            }
            if (text.startsWith("{!", i)) {
                int end = closing(text, i), keyEnd = text.indexOf("!|", i + 2);
                if (end >= 0 && keyEnd >= 0 && keyEnd < end) {
                    pieces.add(new Literal(literal.toString())); literal.setLength(0);
                    pieces.add(new Choice(text.substring(i + 1, end))); i = end + 1; continue;
                }
            }
            literal.append(ch); ++i;
        }
        pieces.add(new Literal(literal.toString()));
        return pieces;
    }
    private static String renderPieces(java.util.List<Piece> pieces, Values values) {
        StringBuilder result = new StringBuilder();
        for (Piece piece : pieces) result.append(piece.render(values));
        return result.toString();
    }
    private static String expandText(AbstractCard card, String text) { return renderPieces(parse(text), new Values(card)); }

    public static Integer getVarFromDynvarKey(AbstractCard c, String dynvarKey) {
        Integer var = null;
        if (dynvarKey.equals("!D!")) {
            //Uses !D! for damage, just like normal dynvars, same applies to !B! and !M!
            var = c.isDamageModified && !DisplayingUpgradesField.displayingUpgrades.get(c) ? c.damage : CardModifierManager.modifiedBaseValue(c, c.baseDamage, "D");
        } else if (dynvarKey.equals("!B!")) {
            var = c.isBlockModified && !DisplayingUpgradesField.displayingUpgrades.get(c) ? c.block : CardModifierManager.modifiedBaseValue(c, c.baseBlock, "B");
        } else if (dynvarKey.equals("!M!")) {
            var = c.isMagicNumberModified && !DisplayingUpgradesField.displayingUpgrades.get(c) ? c.magicNumber : CardModifierManager.modifiedBaseValue(c, c.baseMagicNumber, "M");
        } else if (dynvarKey.equals("!Location!")) {
            //Used to grab the location of the card. Isn't a real dynvar, but we can pretend
            var = -2; //Compendium or otherwise not in a run
            if (CardCrawlGame.dungeon != null && AbstractDungeon.player != null) {
                if (AbstractDungeon.player.masterDeck.contains(c)) {
                    var = -1;
                } else if (AbstractDungeon.player.hand.contains(c) || AbstractDungeon.player.limbo.contains(c) || AbstractDungeon.player.cardInUse == c) {
                    var = 0;
                } else if (AbstractDungeon.player.drawPile.contains(c)) {
                    var = 1;
                } else if (AbstractDungeon.player.discardPile.contains(c)) {
                    var = 2;
                } else if (AbstractDungeon.player.exhaustPile.contains(c) || ExhaustViewFixField.exhaustViewCopy.get(c)) {
                    //This is where we need the field. Without it this will default back to -1 as the cards shown in the Exhaust View are copies that aren't actually in the exhaust pile
                    var = 3;
                } else {
                    //This will cover any time the player does not actually own the card (Shop / Reward / Events)
                    var = 4;
                }
            }
        } else if (dynvarKey.equals("!Upgrades!")) {
            //Used to grab the amount of times the card was upgraded. Isn't a real dynvar
            var = c.timesUpgraded;
        } else if (dynvarKey.equals("!Turn!")) {
            //Used to grab the turn amount. Isn't a real dynvar
            var = -1;
            if (AbstractDungeon.player != null) {
                var = GameActionManager.turn;
            }
        } else if (BaseMod.cardDynamicVariableMap.containsKey(dynvarKey.replace("!",""))) {
            //Check to see if it's a recognized dynvar registered by some mod
            var = BaseMod.cardDynamicVariableMap.get(dynvarKey.replace("!","")).value(c);
        } else if (customChecks.containsKey(dynvarKey)) {
            var = customChecks.get(dynvarKey).apply(c);
        }
        return var;
    }

    public static String unwrap(AbstractCard c, String key) {
        //Cut the leading { and the trailing } and then split the string along each |
        key = key.substring(1, key.length()-1);
        String[] parts = key.split("\\|");
        //Our first piece will always be the dynamic variable we care about. Find its value
        Integer var = getVarFromDynvarKey(c, parts[0]);
        //Clean up the first string since we don't need it
        parts = Arrays.copyOfRange(parts, 1, parts.length);
        //If we found a var then we can do stuff, else just return an empty string
        key = "";
        if (var != null) {
            //Define a matched flag. Lets us know to NOT overwrite the output string with the default output if it actually matched a case
            boolean matched = false;
            //Iterate each case. Note that the right most matching case will be the output string, or the default output if no cases match
            for (String s : parts) {
                //All cases need to contain a single =, which we use for splitting the case into its values and output
                if (s.contains("=")) {
                    String[] split = s.split("=");
                    //Check if the condition has commas, an indicator of a case having multiple conditions.
                    if (split[0].contains(",")) {
                        String[] numbers = split[0].split(",");
                        //Iterate each condition, as long as at least 1 condition matches we set the text
                        for (String n : numbers) {
                            //Checking the length allows up to know if there is actual text or just an empty string
                            String value = checkMatch(var, n, split.length > 1 ? split[1]: "");
                            if (value != null) {
                                key = value;
                                matched = true;
                            }
                        }
                    } else {
                        //Else just check the condition directly
                        String value = checkMatch(var, split[0], split.length > 1 ? split[1]: "");
                        if (value != null) {
                            key = value;
                            matched = true;
                        }
                    }
                    //If this is the default output designated by @= then set this as the output text if we haven't matched anything else yet.
                    if (split[0].equals("@") && !matched) {
                        if (split.length > 1) {
                            key = split[1];
                        } else {
                            key = "";
                        }
                    }
                }
            }
        }
        return key;
    }

    private static String checkMatch(Integer var, String s, String value) {
        //Repeat check
        if (s.equals("repeat")) {
            if (var > 0) {
                return StringUtils.repeat(value, var);
            }
            return "";
        }
        //Greater Than, Less Than, Divisible By, and Ends With are the 4 supported conditional checks, in addition to Direct Match, which has no symbol attached
        boolean greater = s.contains(">");
        boolean less = s.contains("<");
        boolean mod = s.contains("%");
        boolean ends = s.contains("&");
        //Remove all these special symbols before checking if the condition is a number we can make
        s = s.replace(">", "").replace("<", "").replace("%", "").replace("&","");
        if (NumberUtils.isCreatable(s)) {
            //Grab our var minus the number, helpful for comparisons
            int comp = var.compareTo(NumberUtils.createInteger(s));
            //Checks the Direct Match, Greater Than, and Less Than cases
            boolean signCheck = !greater && !less && comp == 0 || greater && comp > 0 || less && comp < 0;
            //Checks the Divisible By case. If the numbers are equal (comp is 0), or if variable mod N is 0, then its divisible
            boolean moduloCheck = mod && (comp == 0 || var % NumberUtils.createInteger(s) == 0);
            //Checks the Ends With case. If the numbers are equal, or if the trailing digits of comp are all 0's, then var ends with N
            boolean digitCheck = ends && (comp == 0 || comp % Math.pow(10, s.length()) == 0);
            //As long as at least one condition matches we are good
            if (signCheck || moduloCheck || digitCheck) {
                return value;
            }
        }
        //The input doesn't match any cases above
        return null;
    }
}
