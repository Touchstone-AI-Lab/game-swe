# Harbor workspace

The mod to repair is the source tree in `/app/mod`; the verifier grades that directory.

# DST Fixed: gifts and bundles misbehave when they are opened from an inventory

## Context

`/app/mod` is **DST Fixed** (Chinese name 纯净辅助, Apache-2.0), a Don't Starve
Together server mod by Ducklantis, at a recent upstream release. It is a
collection of small optional modules. Each module has a configuration option in
`modinfo.lua`, and `modmain.lua` loads the modules whose option is enabled.

Our dedicated server runs the mod with these two modules active and every other
option at its default:

- **Show Bundle** (`BUNDLE`, on by default). Hovering a bundle, a gift or a
  similar wrapped item shows a preview of what is inside. The client asks the
  server for the preview with the mod's `ShowBundle` request, and the server
  replies with one entry per wrapped item (its prefab, its inventory image, its
  stack size and so on).
- **Inventory Unwrap** (`SMARTUNWRAP`, switched on by us). When a bundle that is
  in an inventory or a chest is opened, its contents go into that inventory or
  chest instead of falling on the ground.

## Reports from the server

> Winter's Feast gifts with a surprise inside, the ones that are supposed to
> let a hound or another creature out when they are opened, do nothing when a
> player opens them from the inventory. No creature appears. Instead, something
> odd and invisible turns up in the opener's inventory.

> We run a scenario that reacts when a bundle or gift is opened. It works when
> the bundle is opened on the ground. It never hears about bundles that are
> opened from an inventory or a chest.

> Bundles that the game wraps by itself show a preview full of blank slots, and
> hovering them has crashed some players' clients. Frostjaw's loot bundle is
> one example. The bundles we wrap by hand are fine.

> We updated a while ago, but bundles that were saved back when the preview
> was broken still show blank previews.

> In a bundle's preview, Rot sits on a plain slot. In the inventory it has the
> brown spoiled background. Fresh food in the preview still shows its
> spoilage.

## Expected behaviour

- The base game announces every unwrap. The bundle fires `unwrapped` with
  `{ doer = <opener> }`, and every item that comes out fires `unwrappeditem`
  with `{ bundle = <the bundle>, doer = <opener> }`. A bundle opened from an
  inventory or a chest with Inventory Unwrap active must announce itself in
  exactly the same way.
- A surprise-gift item (the base game's `giftsurprise`) must never be put into
  an inventory. It is dropped the way the base game drops it. A surprise that
  carries a creature therefore releases exactly that creature next to the
  opener, the filler surprises disappear, and no `giftsurprise` stays in the
  inventory.
- Everything else that comes out of a held bundle still goes into the
  inventory or chest the bundle was in. That includes ordinary items, live
  creatures that can be carried (a butterfly, for example), and items that
  cannot normally be picked up by hand (Moongleam, for example). A bundle
  opened on the ground still drops its items exactly as the base game does.
- The preview the server sends for a bundle lists every wrapped item in wrap
  order, and each entry gives the item's prefab and inventory image. This
  holds whether the bundle was wrapped from item entities or from a list of
  prefab names, which the base game's wrapping also accepts.
- When a saved bundle whose stored preview has blank entries is loaded, its
  preview is rebuilt from the items the bundle actually contains.
- Each preview entry carries what the mod's preview tile needs to draw the
  item the way the inventory draws it. An item that the inventory shows on the
  spoiled background (Rot, for example) is shown on that background in the
  preview too. Fresh food keeps its spoilage, and items without either stay on
  a plain slot.

## Evaluation

The verifier runs the mod on a real Don't Starve Together dedicated server
(Steam app 343050, build 24700372), offline, with the configuration above. A
Wilson spawned on the server stands in for the player. The verifier wraps
bundles and gifts with the base game's `unwrappable` component, gives them to
that player or puts them in a chest, and opens them as that player. It listens
for the events above and checks where the contents end up. It asks for
previews through the mod's own `ShowBundle` request handler and reads the reply
the server would send to the client, including the fields the mod's preview
tile (`scripts/widgets/sbitemtile.lua`) reads. It also loads bundles from save
data.
