# DarkRP: reports about money

You are working on **DarkRP**, a Garry's Mod roleplay gamemode written in GLua.
The gamemode source is at `/app/darkrp`.

## Problem

The reports below came in from server owners and players after this branch went out.
They are all about money — what people can pay for, what arrives when it changes hands,
and what the server records about it. They are observations, not diagnoses: nobody who
filed one knew which part of the gamemode was responsible, and they are not all the same
underlying issue.

> **[#6101]** People can buy things they cannot quite pay for. When the price is not a
> whole number and it lands just above what someone is carrying, the purchase goes
> through anyway and they are left holding less than nothing. Whole prices behave
> perfectly.

> **[#6104]** Our accounting add-on has gone blind. It records every change to a
> wallet along with what the wallet held beforehand, and the "beforehand" figure is now
> always identical to the figure afterwards, so there is nothing left to reconcile
> against. The balances themselves are all correct — it is only what we are told about
> them that is wrong.

> **[#6107]** An absurdly large pile of cash comes out as a debt. Put an enormous sum on
> the floor and what lands there is a negative figure instead. Ordinary sums are fine,
> and the threshold where it flips is not one we chose.

> **[#6110]** Cash that a player put down is no longer treated as cash by anything that
> asks. Piles the server itself creates are still recognised, so it is specifically the
> ones that came out of somebody's pocket that have stopped counting.

> **[#6113]** Feeding a wallet something that is not a number now brings down the whole
> call with a Lua error. It used to shrug and refuse. One of our add-ons passes through
> a value it has not sanitised and this turned a harmless no-op into a crash.

> **[#6116]** Setting an allowance to zero used to mean "as many as you like". It now
> means nobody may place a single one. We use zero on purpose for the things we do not
> want to cap, and every one of those is now completely blocked.

> **[#6119]** Handing money to another player does not deliver it. The giver ends up
> with exactly what they started with and the receiver gets nothing at all, so the
> money neither moves nor disappears — the whole exchange simply does not happen.

## What to do

Work in `/app/darkrp`. Resolve everything reported above.

Notes:

- These are symptoms, not diagnoses. Expect to spend real effort locating each cause;
  the wording of a report is not a hint about which file to open.
- Fix the causes. Do not paper over a symptom by special-casing the exact scenario in
  a report, and do not change a caller to work around a helper that is behaving
  incorrectly — other callers use the same helper.
- Do not change anything under `/tests`, and do not add test files of your own to the
  gamemode.
- Behaviour that already works must keep working. These routines are used throughout
  the gamemode and by third-party addons, so a change that fixes one report and breaks
  an unrelated caller is not a fix.
