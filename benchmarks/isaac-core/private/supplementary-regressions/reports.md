# Supplementary Exodus reports

Private maintenance material. Each block below is copied verbatim into the exam of every
derived task whose starter carries the matching `<id>.patch`. The patches apply to the
composite reference tree (`main.lua`, sha256 `ee5753ae…`); the reference repair of a report is
the reverse of its patch.

> **[#EX-406]** In runs where Welcome Mat has been picked up, things that should appear in
> place start shooting across the room once the first mat has been laid. Baseball Mitt's
> impact poof, for example, streaks away the moment a released ball lands instead of popping
> where it hit. Other effects and pickups that Exodus spawns at rest are thrown the same way.
> The mat itself still lays down and still gives its tears bonus when the character stands
> on it.

> **[#EX-412]** Welcome Mat gets floor changes wrong. Arriving on a new floor now lays a mat
> under the character in the floor's first room, although nobody walked in through a door.
> The next room entered after that gets no mat at all, so its tears bonus is missing there;
> from the room after that, mats appear as usual. A mat belongs in every room entered after
> the first room of a floor, including the very next one, and never in the room where a new
> floor begins.

> **[#EX-427]** Lil Rune no longer takes on the power of runes. Using a rune while holding
> Lil Rune leaves the familiar unchanged: no transformation animation plays and none of the
> rune powers appear — for example, after Algiz it should destroy enemy shots that touch it,
> and after Jera it should split dying enemies.

> **[#EX-436]** Child's Leash has no effect on Exodus's orbiting familiars. While the trinket
> is held, Sundial's sun and shadow, Hungry Hippo and Robo-Baby 3.6.0 keep circling at their
> full distance instead of being pulled in to half of it. They must orbit at half their
> usual distance while Child's Leash is held, and return to their usual distance once it is
> dropped.

> **[#EX-441]** Ominous Lantern now costs its charge just for being put away. Raising the
> lantern and then using the item again to lower it, without throwing, leaves the item empty:
> it cannot be raised again until its slow recharge (about ten seconds) has run. Lowering a
> lantern that was never thrown should leave it ready to raise again straight away. Throwing
> it must still empty it and start that recharge as before.

> **[#EX-447]** Hurdle Heels' landing stomp no longer hurts enemies. An enemy standing right
> next to Isaac when he comes down from the jump takes no damage at all.

> **[#EX-452]** A new run started without closing the game inherits the previous run's stat
> changes. After using The Forbidden Fruit or Tragic Mushroom in one run, Isaac starts the next
> run with that run's boosted damage, speed and range; they only drop back to normal once he
> walks into another room. Every new run should start from the character's own stats.

> **[#EX-461]** Big Scissors' blood trail is gone. After Isaac is hurt while holding Big
> Scissors, the item's other effects still kick in, but he no longer leaves a trail of red
> creep behind him for the rest of the room.

> **[#EX-463]** Unholy Mantle's burst no longer hurts enemies. When Isaac is hit while the
> mantle is charged, its costume disappears as before, but the enemies in the room take no
> damage. The burst should hit every vulnerable enemy in the room, once per floor.

> **[#EX-465]** Birdbath does nothing when used: no bath appears next to Isaac.

> **[#EX-467]** Paper Cut no longer makes cards hurt. Using a card while holding Paper Cut
> should cut every vulnerable enemy in the room, but they take no damage at all.

> **[#EX-469]** Balls returned by Baseball Mitt have lost their punch. They no longer bounce
> off walls or confuse enemies, they hit no harder than an ordinary tear, and when several
> shots were caught only one ball comes back.
