# Content Patcher: {{i18n}} rewrites some translations to lowercase

You are working on **Content Patcher**, the SMAPI framework mod that lets Stardew
Valley content packs edit game assets declaratively. The mod's source is at
`/app/StardewMods` (the mod project is `ContentPatcher/`; `Common/` is shared code
used by the same author's mods).

## Problem

Content pack authors report that the `{{i18n}}` token sometimes changes the case
of their translation text. One author writes: "My i18n file has
`\"affirmative\": \"True\"` and the token inserts `true` into the target asset.
Same with `\"FALSE\"` becoming `false`. It only happens when the translation is
one of those words exactly — `\"True enough\"` comes through untouched, and so
does every normal sentence. My pack writes these values into a data asset the
game compares case-sensitively, so the lowercased text breaks it."

## Task

Make the `{{i18n}}` token return translation text exactly as written, including
for translations whose entire text happens to match words Content Patcher treats
specially elsewhere. Token behavior otherwise — defaults, placeholders, tokens
inside translations — must not change.

## Notes

- The game is Stardew Valley 1.6.15 with SMAPI 4.1.10, installed at `/opt/stardew`.
- Build with `dotnet build ContentPatcher/ContentPatcher.csproj -p:GamePath=/opt/stardew`.
- Do not modify anything under `/tests`.
- The grading harness compiles your tree, loads it into the real game headless
  with a small content pack installed, and inspects the patched assets.
