# Official download provider

`rhenium-official-download` is an independent, optional `rhenium.auth_providers`
distribution. It downloads the exact files of an official game or dedicated-server
distribution that is not on Steam, over HTTPS, and keeps a file only when its size
and SHA-256 match the pin in the runtime catalog. AGENTS.md permits this path only
when the game, or its official dedicated server, is distributed outside Steam.

For the complete lifecycle, see
[Managed authentication and runtimes](../../docs/managed-runtimes.md).

## Operator use

```sh
rhenium auth login official-download
rhenium runtime prepare <game-id>/<runtime-id>
```

Login creates an empty, credential-free local session and makes no network request.
It does not verify ownership or accept any licence. Files are downloaded only by
the explicit `runtime prepare` command; evaluation never downloads anything.

## Source schema

```json
{
  "kind": "official-download",
  "files": [
    {
      "name": "server.jar",
      "url": "https://downloads.example.org/releases/1.2.3/server.jar",
      "sha256": "<64 lowercase hexadecimal digits>",
      "size": 12345678
    }
  ],
  "redirectHosts": ["objects.example-cdn.net"],
  "expectedFiles": ["server.jar"],
  "sha256": "<builder pin>"
}
```

- `files` is non-empty. Each `name` is a plain file name: no path, no leading dot,
  and unique without regard to case. Each `url` is an exact `https://` URL with a
  lowercase DNS host name, and no credentials, port, query or fragment. `sha256`
  and `size` (bytes, greater than zero) pin the content.
- `redirectHosts` lists the only other hosts that a redirect may lead to. A file's
  own URL host is always allowed. A redirect is followed one hop at a time, at most
  five times, and only to an `https://` URL on an allowed host with no credentials
  or port. A redirect URL may carry a query, such as a signed download token. A
  redirect anywhere else fails before that host is contacted.
- `expectedFiles` and `sha256` are optional and are passed through to the game's
  runtime builder, which must enforce them itself. This provider does not interpret
  them.
- Unknown fields are rejected.

## Acquisition and cache rules

The provider sends a plain `GET` request with the User-Agent
`rhenium-official-download/<version>` and `Accept-Encoding: identity`. It never
sends an Authorization header, cookie or token. Proxy settings from the
environment (`HTTPS_PROXY` and similar) are honoured.

Each file is streamed into a new hidden `.<name>.partial` file in the provider
cache, `<cache>/providers/official-download/<runtime-fingerprint>/`. The partial
file is created exclusively and with owner-only permissions. A download fails
closed when any of these is true:

- the status is not 200;
- the response has a `Content-Encoding` other than `identity`;
- `Content-Length` differs from the pinned size;
- the body is longer or shorter than the pinned size;
- the SHA-256 differs from the pin;
- a redirect breaks the rules above.

Only when every file of the source has been verified are they linked to their
final names. On a failure the provider removes the partial and final files it
created in that call, so the cache is empty again and the same `runtime prepare`
can be retried.

A cache that already holds exactly the pinned files, each a regular file of the
pinned size and digest, is reused without a request. Any other non-empty cache
fails closed and is never overwritten or deleted by the provider. This includes a
partial download left by an interrupted process, a missing, extra or changed
file, and a symbolic link. Inspect such a cache, then remove it with
`rhenium runtime prune <game-id>/<runtime-id>` before preparing again.

Error and progress messages name only the file and its declared host. They never
quote a redirect URL, because one can contain a signed token.

## Integrity boundary

The SHA-256 pin in the reviewed runtime catalog protects content selection: a
substituted, truncated or changed download is rejected. It is not a publisher
signature, and this provider does not verify one. HTTPS protects the transfer.
Downloaded files are kept only in ignored local state. A public download grants no
redistribution right, and a game's own licence terms, such as an end-user
agreement, remain the operator's decision and the game plugin's responsibility.

## Tests

Unit tests use `httpx.MockTransport` as a fake HTTPS origin. They need no network,
account or real distribution:

```sh
pytest -q providers/official-download/tests
```
