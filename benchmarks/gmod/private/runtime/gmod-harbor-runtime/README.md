# GMod Addons Harbor verifier runtime

This is shared verifier infrastructure, not a benchmark task. It packages an
operator-retained Garry's Mod Dedicated Server (Steam app 4020, Linux build
`23150012`) together with the repository's own Addons evaluator. No Facepunch or
Valve files are stored in Git, and the resulting image is local and must never be
pushed to a registry.

```sh
benchmarks/gmod/private/runtime/gmod-harbor-runtime/build-image.sh /srv/rhenium/gmod-server
```

The script checks `steamapps/appmanifest_4020.acf` for build `23150012` and an
executable `srcds_linux`, then passes the directory to `docker build` as the named
`server` build context and tags `gcb-gmod-addons-verifier:23150012`. The Dockerfile
repeats the build check inside the image. Neither of them logs in to Steam or
downloads, updates or repairs anything.

Why the server is not downloaded during the build: SteamCMD's `app_update` can
request only the currently published build. On 2026-09-21 the public branch of
app 4020 was at build `25375525`, so an anonymous download no longer reproduces
the pin. The pinned installation therefore has to be one the operator retained,
as [the Garry's Mod support guide](../../../../../docs/games/garrys-mod.md#native-linux-runtime)
already requires for the native runner. Do not change the pin or edit the manifest
to accept a newer download.

Pins and their limits:

- The base image is the digest-pinned `ubuntu:24.04` with the i386 loader and
  libraries that the 32-bit `srcds_linux` needs.
- `requirements.txt` pins the evaluator's Python dependencies to the versions in
  the repository `uv.lock`.
- `evaluator/` is a byte-for-byte copy of `src/rhenium/__init__.py`,
  `src/rhenium/core/` and `plugins/garrys-mod/src/rhenium_garrys_mod/`, written by
  `private/harbor/scripts/materialize.py`. A plugin test fails when the copy drifts,
  but nothing checks an already built image: the image keeps the copy it was built
  from, and its tag does not change with it. Rebuild the image whenever `evaluator/`
  changes. Catalog 2.2.0, for example, needs an evaluator that compares each exam
  heading with `title.en`; an image built before 2.2.0 fails every 2.2.0 task closed.
- The server and `/opt/gmod/state` live in one image filesystem because the native
  runner builds its per-phase server views from hard links. In a container the
  first link of each file copies it up from the image layer, so the first phase of
  every verifier run pays for one copy of the installation.

This image is not a Rhenium managed runtime. The Hub still evaluates
`garrys-mod/addons` with the plugin-owned native runner configured through
`RHENIUM_PLUGIN_GMOD_SERVER_ROOT`; the image serves Harbor trials and the
`private/harbor/scripts/validate-*.sh` controls.
