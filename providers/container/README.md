# Rhenium public-container provider

`rhenium-container` is an independent Rhenium source provider for publicly
readable, digest-pinned container images. It never accepts or stores credentials.
Its `auth login` operation creates an empty anonymous session because Rhenium's
runtime lifecycle currently resolves every source through the auth-provider
contract.

For the complete lifecycle, see
[Managed authentication and runtimes](../../docs/managed-runtimes.md).

## Installation and operator use

The repository development environment installs all workspace distributions:

```sh
devenv shell
rhenium auth list
rhenium auth login container
rhenium runtime prepare <game-id>/<runtime-id>
```

The provider requires a working Docker CLI and daemon. Login performs no Docker
operation and raises no challenge; image acquisition happens only during the
explicit `runtime prepare` command.

## Source schema

The provider accepts this `RuntimeSpec.source` shape:

```json
{
  "kind": "container-image",
  "image": "ghcr.io/example/runtime@sha256:<64-lowercase-hex>",
  "expectedFiles": ["path/inside/image"]
}
```

`kind` must be `container-image`, and `image` must use a digest rather than a
tag. The provider pulls that exact reference, checks that Docker reports the
pinned repository digest, obtains the immutable local image ID, and writes this
record into Rhenium's provider cache:

```json
{
  "schemaVersion": 1,
  "image": "ghcr.io/example/runtime@sha256:<digest>",
  "imageId": "sha256:<local-content-id>",
  "repoDigests": ["ghcr.io/example/runtime@sha256:<digest>"]
}
```

The record is not sufficient evidence by itself. A consuming game builder must
require its `image` to equal the catalog source, compare `imageId` with a fresh
Docker inspection, and validate every declared `expectedFiles` entry. The
Garry's Mod builder additionally binds the source reference, task build-context
digest and runtime fingerprint into labels on each derived evaluator image. It
never adopts an image merely because a predictable local tag exists.

## Integrity boundary

The pinned repository digest protects source selection, while the recorded
local image ID and derived-image IDs identify the exact content Rhenium will
execute. This provider does not attest the publisher, scan image contents, make
mutable tags safe, or make unpinned package downloads inside a downstream
Dockerfile reproducible.

Tests use fake Docker command results and require neither a registry connection
nor a real image:

```sh
pytest -q providers/container/tests
```
