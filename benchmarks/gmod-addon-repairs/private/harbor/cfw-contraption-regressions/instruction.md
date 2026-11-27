# Contraption Framework: reports about contraption tracking

You are working on **Contraption Framework (CFW)**, the Garry's Mod server addon that
watches constraints and parenting, groups connected entities into contraption objects
(`ent:CFW_GetContraption()`) and parented entities into families (`ent:GetFamily()`),
and keeps running totals such as `totalMass` on those objects so other addons do not
have to walk every entity. The addon source is at `/app/cfw`.

## Problem

The reports below came in from the developers of addons built on CFW and from server
operators after this build went out. They are observations, not diagnoses: nobody who
filed one knew which part of the addon was responsible, and they are not all the same
underlying issue.

> **[A]** The `totalMass` of a family goes stale. When the mass of one of its members is
> changed after the family was formed (a weight tool, or an addon calling
> `SetMass` on the member's physics object), the contraption's `totalMass` follows the
> change but the family's `totalMass` keeps the old value, and later additions and
> removals drift further from the truth. A family's total should follow its members'
> masses just like a contraption's does.

> **[B]** An entity cannot refuse children with the `CFW_PreParented` hook alone.
> Returning `false` from it is ignored and the child is parented anyway; the veto only
> works on entities that also define `CFW_OnParented`. Defining `CFW_PreParented` on its
> own must be enough to be asked, and to refuse.

> **[C]** Parenting a prop to a character - a player, an NPC or a nextbot (hats,
> attachments, carried props) - pulls that character into a contraption together with
> the prop. Characters must never become part of a contraption through parenting, and a
> prop parented to one must not form a contraption with it.

> **[D]** Welding or roping one bone of a ragdoll to another bone of the same ragdoll
> turns that ragdoll into a contraption with a link to itself. Such a constraint joins
> an entity to itself and links nothing: it must not create a link or a contraption.

## What to do

Work in `/app/cfw`. Resolve everything reported above.

Notes:

- These are symptoms, not diagnoses. Expect to spend real effort locating each cause;
  the wording of a report is not a hint about which file to open.
- Fix the causes. Do not special-case the exact scenario in a report; every addon that
  builds on CFW relies on the same tracking.
- Do not change anything under `/tests`, and do not add test files of your own to the
  addon.
- Behaviour that already works must keep working: welded and parented props must still
  form contraptions and families, split when their links go, and keep their totals.
