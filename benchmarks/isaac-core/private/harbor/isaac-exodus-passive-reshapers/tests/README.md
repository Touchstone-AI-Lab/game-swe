# Verifier

Since catalog 5.0.0 this task runs the shared 54-case, three-process verifier in
`../../verifiers/exodus-v2/`: the frozen composite's suites plus the cases that observe the
supplementary regressions (see that directory's README). The Hub still builds the verifier
image from `../isaac-exodus-release-regressions/tests/` and binds every task in this pack to
the same `afterbirth-plus-1.06.t1` runtime artifact; for this task it mounts the shared
`test.sh` and three suites read-only over the image's copies. `test.sh` here is a byte copy
of the shared one, kept so the catalog loader can read the declared case list; the loader
rejects a copy that drifts, so edit the shared verifier, not this file.

`run-game.sh` here is this task's launch script. The Hub mounts it read-only over the
image's `/tests/run-game.sh`; the frozen task keeps the copy baked into the image. It
differs from the frozen script only in how the offline Steam client is started and asked
to launch the game:

- It sends the launch request as soon as the client proper is up (its `Client version`
  console line) instead of as soon as any Steam process exists. A request forwarded to the
  bootstrapper while it verifies or updates itself is dropped; one queued with the running
  client is taken when its startup finishes. On a host with a saturated disk the client
  took 40 to 260 seconds to start, and the frozen script's immediate request was often
  dropped, so the game never started (2026-09-23 UTC, see the task's `validation/README.md`).
- If the client has not taken a request 60 seconds after its `System startup time` line,
  the request is sent once more. A client that takes neither is killed and replaced, up
  to four client starts per game process; in the observed cases such a client kept logging
  `SteamUI thread frame stalled` and never processed another forwarded command. `steam.sh -shutdown` is
  only sent to a working client, because with no client left it starts a new one. A client
  that does not exit within 60 seconds of it is killed and its `steam.pid` and `steam.pipe`
  removed.
- Its wall-clock budgets are longer: 420 seconds each for the client proper to appear and
  to finish starting, 240 seconds for the game process after the client took the request,
  60 Return presses to reach the run, and 900 seconds for a suite. The suites count game
  frames, not wall-clock time.

Exit codes 10 to 13 and the `GCB_RUNTIME_INVALID` markers keep the frozen meanings, and a
retry happens only before the game process exists, so the submitted mod cannot influence
it. The copies under the nine derived tasks are byte-identical; the plugin tests check
that and that everything from the key presses on matches the frozen script except the two
budgets.
