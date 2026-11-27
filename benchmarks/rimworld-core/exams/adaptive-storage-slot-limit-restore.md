# Restore a saved storage slot limit after loading

The supplied source uses a fixed native RimWorld 1.6 upstream baseline with the
historical slot-limit regression reconstructed at the initialization transition.
It is not a byte-exact historical upstream base. Repair the behavior described below in
`AdaptiveStorage/Source`. The task uses RimWorld Core plus Harmony only; do not add
DLC or another Mod dependency.

Required behavior:

- Capture the saved logical slot limit during post-initialization and restore that exact backing value through the real CurrentSlotLimit property setter.
- Before invoking the setter, make the backing value different from the saved value so the setter cannot return early. The build disables overflow checking (`CheckForOverflowUnderflow=false`, C# 12). A temporary unchecked wrap is permitted; it must not throw, leak into the restored backing value, or change the final effective capacity. No particular increment, sentinel or source line is required.
- `int.MaxValue` is the logical unlimited sentinel: it is valid both as saved input and as the final backing value. The public CurrentSlotLimit getter returns the saved limit capped by TotalSlots. For example, unlimited on four one-slot cells retains the sentinel but exposes an effective limit of four. A temporary transition value must never become the saved logical result.
- Recompute the per-cell limit and dependent storage bookkeeping through the existing setter path.
- Preserve zero, one-slot, ordinary finite, near-int.MaxValue, multi-cell, already-unlimited, default and repeated-initialization behavior.
- Initialization must complete, including per-cell collections, a usable renderer, the completion event, and settings/slot notifications. Returning after catching an internal initialization error is not successful initialization. Repeating initialization must again complete and preserve capacities; this task does not require a particular private field layout or deduplication of historical event subscriptions.
- Do not bypass the setter or change unrelated packing, rendering, temperature-control, storage-filter, or serialization behavior.

The scored surface is `ThingClass.PostInitialize slot-limit transition`. Keep unrelated upstream behavior intact.
Do not add RimWorld, Unity or Harmony binaries, generated output, test results,
credentials, Workshop content, assets, saves, or logs. The private evaluator owns
the pinned references and expected results and runs with networking disabled.
