# Result-mutation probe

> Historical round-3 control. This file records the in-body marker design at PR
> commit `4b12283`; that design was superseded because asynchronous expectation
> failures are recorded only when GLuaTest's original `done()` runs. The current
> evaluator snapshots results inside a patched private runner before public hooks and
> is validated in [`rhenium-controls.md`](rhenium-controls.md). The JSON beside this
> file is preserved as historical evidence, not a current result schema.

The append-only probe next to this file covers a submission that *adds* a forged
transcript. It does not cover the more direct attack: GLuaTest's runner calls the
`GLuaTest_LogTestResult` hook **before** a result is stored or printed, so a
submission can rewrite a failing result into a passing one and the framework then
emits an ordinary, exactly-once passing transcript. Counting framework output cannot
detect that.

## The attack

Base tree — every defect present, so the suite genuinely fails — plus this appended
to `gamemode/init.lua`:

```lua
local realAdd = hook.Add          -- cached before the suite can block it
local function gcbForge()
    realAdd( "GLuaTest_LogTestResult", "gcb_forge", function( result )
        result.success = true
        result.errInfo = nil
    end )
end
gcbForge()
timer.Simple( 0, gcbForge )       -- re-register after the suite removes it
timer.Simple( 0.5, gcbForge )
```

## Result

`reward=0`. The recorded verdict is in `result-mutation-probe.result.json`:

| channel | value |
|---|---|
| framework PASS lines | 6 |
| in-body collector markers | 4 |
| cases the collector refused to confirm | 7 |

The two channels disagree, and the verifier requires them to agree per case. The
suite's removal of the hook blunted part of the attack and the re-registration
restored part of it — which is why the framework reports six passes on a tree that
fixes nothing — but no case was ever confirmed that did not actually reach the end
of its own body.

## Why the collector cannot be produced by mutating a result

The markers are emitted from inside the case body: for a synchronous case after its
last assertion returned, for an asynchronous one at the moment it calls `done()`. A
failing assertion throws before the marker is reached. Rewriting the stored result
changes what the framework prints; it cannot retroactively execute the rest of a case
body that already aborted.

## Residual limit, stated plainly

Code in the same Lua state can read the staged suite and therefore the per-run nonce.
That raises forgery from "print a transcript" to "read the staged suite, suppress the
real marker, and emit a matching one" — it does not make it impossible. No verifier
that parses a log written by the process under test can. The honest claim is that
both documented attacks are closed and that a third would have to be substantially
more elaborate and would still have to survive the exactly-once counting.
