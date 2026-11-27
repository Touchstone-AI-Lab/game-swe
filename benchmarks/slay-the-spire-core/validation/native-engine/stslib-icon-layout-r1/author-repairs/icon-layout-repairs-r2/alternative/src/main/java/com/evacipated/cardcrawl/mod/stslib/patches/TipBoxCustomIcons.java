package com.evacipated.cardcrawl.mod.stslib.patches;

import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.g2d.BitmapFont;
import com.badlogic.gdx.graphics.g2d.GlyphLayout;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.evacipated.cardcrawl.mod.stslib.icons.AbstractCustomIcon;
import com.evacipated.cardcrawl.mod.stslib.icons.CustomIconHelper;
import com.evacipated.cardcrawl.modthespire.lib.*;
import com.megacrit.cardcrawl.core.Settings;
import com.megacrit.cardcrawl.helpers.FontHelper;
import com.megacrit.cardcrawl.helpers.PowerTip;
import com.megacrit.cardcrawl.helpers.TipHelper;
import javassist.CtBehavior;

import java.util.ArrayList;

public class TipBoxCustomIcons {

    private static final float CARD_ENERGY_IMG_WIDTH = 24.0f * Settings.scale;

    @SpirePatch(clz= TipHelper.class, method="renderPowerTips")
    public static class DontYeetPowerIcon {
        @SpirePrefixPatch public static void begin() { headers.get().push(new java.util.IdentityHashMap<PowerTip,String>()); }
        @SpireRawPatch public static void restoreOnExit(CtBehavior behavior) throws javassist.CannotCompileException {
            behavior.insertAfter("com.evacipated.cardcrawl.mod.stslib.patches.TipBoxCustomIcons.restoreHeaders();", true);
        }
        @SpireInsertPatch(locator = Locator.class, localvars = {"tip"})
        public static void StopThat(float x, float y, SpriteBatch sb, ArrayList<PowerTip> powerTips, @ByRef PowerTip[] tip) {
            String[] words = tip[0].header.split(" ");
            boolean modified = false;
            for (int i = 0 ; i < words.length ; i++)
            if (words[i].length() > 0 && words[i].charAt(0) == '[') {
                String key = words[i].trim();
                if (key.endsWith(AbstractCustomIcon.CODE_ENDING)) {
                    key = key.replace("*d", "D").replace("*b", "B").replace("*m", "M");
                }
                AbstractCustomIcon icon = CustomIconHelper.getIcon(key);
                if (icon != null) {
                    words[i] = "   ";
                    modified = true;
                }
            }
            if (modified) {
                saveHeader(tip[0]);
                tip[0].header = String.join(" ", words);
            }
        }

        private static class Locator extends SpireInsertLocator {
            @Override
            public int[] Locate(CtBehavior ctBehavior) throws Exception {
                Matcher matcher = new Matcher.MethodCallMatcher(GlyphLayout.class, "setText");
                return LineFinder.findInOrder(ctBehavior, matcher);
            }
        }
    }

    @SpirePatch(clz= FontHelper.class, method="renderSmartText", paramtypez = {SpriteBatch.class, BitmapFont.class, String.class, float.class, float.class, float.class, float.class, Color.class})
    public static class FontHelpFixes {
        @SpireInsertPatch(locator = Locator.class, localvars = {"word"})
        public static void DrawIconsPls(SpriteBatch sb, BitmapFont font, String msg, float x, float y, float lineWidth, float lineSpacing, Color baseColor, @ByRef float[] ___curWidth, @ByRef float[] ___curHeight, @ByRef String[] word) {
            if (word[0].length() > 0 && word[0].charAt(0) == '[') {
                String key = word[0].trim();
                if (key.endsWith(AbstractCustomIcon.CODE_ENDING)) {
                    key = key.replace("*d", "D").replace("*b", "B").replace("*m", "M");
                }
                AbstractCustomIcon icon = CustomIconHelper.getIcon(key);
                if (icon != null) {
                    if (___curWidth[0] + CARD_ENERGY_IMG_WIDTH > lineWidth) {
                        ___curHeight[0] -= lineSpacing;
                        icon.render(sb, x, y+___curHeight[0], icon.region.getRegionWidth()/2F, -icon.region.getRegionHeight()/4F, Settings.scale, 0);
                        ___curWidth[0] = CARD_ENERGY_IMG_WIDTH;
                    } else {
                        icon.render(sb, x+___curWidth[0], y+___curHeight[0], icon.region.getRegionWidth()/2F, -icon.region.getRegionHeight()/4F, Settings.scale, 0);
                        ___curWidth[0] += CARD_ENERGY_IMG_WIDTH;
                    }
                    word[0] = "";
                }
            }
        }

        private static class Locator extends SpireInsertLocator {
            @Override
            public int[] Locate(CtBehavior ctBehavior) throws Exception
            {
                Matcher matcher = new Matcher.MethodCallMatcher(FontHelper.class, "identifyOrb");
                return LineFinder.findInOrder(ctBehavior, matcher);
            }
        }
    }

    @SpirePatch(clz= FontHelper.class, method="exampleNonWordWrappedText", paramtypez = {SpriteBatch.class, BitmapFont.class, String.class, float.class, float.class, Color.class, float.class, float.class})
    public static class FontHelpFixesZHS {
        @SpireInsertPatch(locator = Locator.class, localvars = {"word"})
        public static void DrawIconsPls(SpriteBatch sb, BitmapFont font, String msg, float x, float y, Color baseColor, float lineWidth, float lineSpacing, @ByRef float[] ___curWidth, @ByRef int[] ___currentLine, @ByRef String[] word) {
            if (word[0].length() > 0 && word[0].charAt(0) == '[') {
                String key = word[0].trim();
                if (key.endsWith(AbstractCustomIcon.CODE_ENDING)) {
                    key = key.replace("*d", "D").replace("*b", "B").replace("*m", "M");
                }
                AbstractCustomIcon icon = CustomIconHelper.getIcon(key);
                if (icon != null) {
                    if (___curWidth[0] + CARD_ENERGY_IMG_WIDTH > lineWidth) {
                        ___currentLine[0] += 1;
                        icon.render(sb, x, y - ___currentLine[0] * lineSpacing, icon.region.getRegionWidth()/2F, -icon.region.getRegionHeight()/4F, Settings.scale, 0);
                        ___curWidth[0] = CARD_ENERGY_IMG_WIDTH;
                    } else {
                        icon.render(sb, x+___curWidth[0], y - ___currentLine[0] * lineSpacing, icon.region.getRegionWidth()/2F, -icon.region.getRegionHeight()/4F, Settings.scale, 0);
                        ___curWidth[0] += CARD_ENERGY_IMG_WIDTH;
                    }
                    word[0] = "";
                }
            }
        }

        private static class Locator extends SpireInsertLocator {
            @Override
            public int[] Locate(CtBehavior ctBehavior) throws Exception
            {
                Matcher matcher = new Matcher.MethodCallMatcher(FontHelper.class, "identifyOrb");
                return LineFinder.findInOrder(ctBehavior, matcher);
            }
        }
    }

    public static AbstractCustomIcon lookup(CharSequence text) {
        if (text == null) return null;
        String key = text.toString().trim().replace("*d", "D").replace("*b", "B").replace("*m", "M");
        return CustomIconHelper.getIcon(key);
    }
    public static CharSequence headerForMeasurement(CharSequence text) {
        String[] words = text.toString().split(" ", -1);
        for (int i = 0; i < words.length; i++) if (lookup(words[i]) != null) words[i] = "   ";
        return String.join(" ", words);
    }


    @SpirePatch(clz=FontHelper.class, method="getSmartHeight", paramtypez={BitmapFont.class,String.class,float.class,float.class})
    @SpirePatch(clz=FontHelper.class, method="getSmartWidth", paramtypez={BitmapFont.class,String.class,float.class,float.class})
    public static class CustomMetrics {
        @SpireInstrumentPatch
        public static javassist.expr.ExprEditor metrics() {
            return new javassist.expr.ExprEditor() {
                public void edit(javassist.expr.MethodCall call) throws javassist.CannotCompileException {
                    if (call.getClassName().equals(GlyphLayout.class.getName()) && call.getMethodName().equals("setText")
                            && call.getSignature().equals("(Lcom/badlogic/gdx/graphics/g2d/BitmapFont;Ljava/lang/CharSequence;)V")) {
                        call.replace("{ $proceed($$); if (com.evacipated.cardcrawl.mod.stslib.patches.TipBoxCustomIcons.lookup($2) != null) $0.width = 24.0F * com.megacrit.cardcrawl.core.Settings.scale; }");
                    }
                }
            };
        }
    }
    @SpirePatch(clz=basemod.patches.com.megacrit.cardcrawl.helpers.FontHelper.FixChineseColoredTextMess.FixGetHeightForChineseText.class, method="PrefixChangeHeight")
    public static class CustomChineseMetrics {
        @SpireInstrumentPatch
        public static javassist.expr.ExprEditor metrics() {
            return new javassist.expr.ExprEditor() {
                public void edit(javassist.expr.FieldAccess field) throws javassist.CannotCompileException {
                    if (field.isReader() && field.getFieldName().equals("CARD_ENERGY_IMG_WIDTH")) {
                        field.replace("{ $_ = com.evacipated.cardcrawl.mod.stslib.patches.TipBoxCustomIcons.lookup(word) != null ? 24.0F * com.megacrit.cardcrawl.core.Settings.scale : $proceed(); }");
                    }
                }
            };
        }
    }

    private static final ThreadLocal<java.util.ArrayDeque<java.util.IdentityHashMap<PowerTip,String>>> headers =
            ThreadLocal.withInitial(java.util.ArrayDeque::new);
    public static void saveHeader(PowerTip tip) { headers.get().peek().putIfAbsent(tip, tip.header); }
    public static void restoreHeaders() {
        java.util.ArrayDeque<java.util.IdentityHashMap<PowerTip,String>> stack = headers.get();
        if (stack.isEmpty()) return;
        java.util.IdentityHashMap<PowerTip,String> saved = stack.pop();
        for (java.util.Map.Entry<PowerTip,String> entry : saved.entrySet()) entry.getKey().header = entry.getValue();
        if (stack.isEmpty()) headers.remove();
    }


    // Patch the semantic helpers themselves. Java 8 callers use synthetic
    // accessors, so matching source-level call names at their call site misses them.
    @SpirePatch(clz=basemod.patches.com.megacrit.cardcrawl.helpers.FontHelper.FixChineseColoredTextMess.class, method="usingEnergyIcon")
    @SpirePatch(clz=basemod.patches.com.megacrit.cardcrawl.helpers.FontHelper.FixChineseColoredTextMess.class, method="identifyOrb")
    public static class CustomChineseDetection {
        @SpirePostfixPatch public static boolean detect(boolean __result, String word) {
            return __result || lookup(word) != null;
        }
    }

}
