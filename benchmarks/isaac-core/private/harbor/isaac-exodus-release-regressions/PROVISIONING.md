# Managed licensed runtime

The Isaac task uses Rhenium's provider and runtime lifecycle. Repository scripts no
longer install host packages, collect Steam credentials, or build mutable image tags.

## Prerequisites

- Linux x86_64 with Docker, Xvfb, and the required user-namespace policy; or
- Windows 11 x86_64 with WSL2 and the managed Rhenium worker; and
- a Steam account that owns Rebirth, Afterbirth, and Afterbirth+.

Run the non-mutating checks first:

```sh
rhenium worker doctor
rhenium runtime doctor isaac-rebirth/afterbirth-plus-1.06.t1
```

Rhenium never installs host packages or enables Windows features. Resolve any failed
doctor checks using the operating system's supported administration workflow.

## Login and preparation

```sh
rhenium auth login steam --account default
rhenium runtime prepare isaac-rebirth/afterbirth-plus-1.06.t1 \
  --account default
```

`auth login steam` displays two Steam Mobile QR codes. The first stores the
persistent Steam session used for depot downloads. The second authorizes the
official Steam client, which the provider runs headlessly in a container and which
Isaac needs because the game keeps Steam DRM; that step also installs Steam Linux
Runtime 1.0 while the client still has network. `prepare` then downloads the three
pinned depots, stages the client state, and boots the game once with no network so
it writes a fresh zero-progression `options.ini`.

This managed path is implemented but has not yet completed a real licensed run.
When the expected client state is absent, `prepare` still returns
`status: action_required`, kind `steam-client-bootstrap`, and exits with status 2.
The response's `details.stateRoot` is the isolated directory to populate and
`details.requiredFiles` names the required Steam client and Isaac `options.ini`
files. The Web UI displays the same action. The manual bootstrap below remains the
documented fallback.

Using the official Steam client outside Rhenium, prepare that exact state root with
Steam Cloud disabled, a fresh zero-progression Isaac profile, one successful launch,
and working Offline Mode. Do not use an account's normal Steam home. This manual
bootstrap is a known integration limitation and must be performed only on the
controlled licensed runtime host. Rerun the same `rhenium runtime prepare` command
after the required files exist; the builder then stages the pinned depots, verifies
`isaac.x64`, and builds the private immutable evaluator image.

A controlled host with an already validated
`gcb-isaac-exodus-verifier:abp-v1.06.t1` image may adopt that exact local image ID.
The image remains private and non-redistributable. Adoption does not remove the
provider login or pinned-source acquisition step from the Hub lifecycle.

The resulting game files, Steam client state, source cache, and Docker images are
non-redistributable and remain on that machine. Do not copy the Rhenium state directory
or publish its images.

## Evaluation and maintenance

```sh
rhenium runtime verify isaac-rebirth/afterbirth-plus-1.06.t1
rhenium run isaac-rebirth/core/isaac-exodus-release-regressions \
  /path/to/submission --profile full
```

Evaluation is offline and resolves the immutable image ID recorded during prepare.
It never downloads or rebuilds a missing runtime. Remove all cached licensed content
only with an explicit confirmation:

```sh
rhenium runtime prune isaac-rebirth/afterbirth-plus-1.06.t1
```
