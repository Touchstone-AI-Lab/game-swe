# Rhenium local Web UI

This directory contains Rhenium's local management console. It is a React 19,
TypeScript, Vite, Tailwind CSS, and shadcn-style component application served by
the Python Hub in production.

The UI manages local benchmark catalog access, Steam QR authentication,
licensed runtimes, operations, runs, reports, and settings. It does
not implement a separate backend or store provider secrets in browser storage.

## Run the production-style UI

Build the bundle and start Rhenium from the repository root:

```sh
npm ci --prefix web
npm run build --prefix web
rhenium web
```

Open <http://127.0.0.1:4317>. `rhenium web` refuses non-loopback bind addresses.
The Python server serves `web/dist/index.html`, mounts hashed assets under
`/assets`, and falls back to the SPA entry point for client-side routes.

Set `RHENIUM_WEB_DIST` only when testing a bundle outside the normal `web/dist`
or packaged-wheel location.

## Development server

Run the Hub and Vite in separate terminals:

```sh
rhenium web
```

```sh
npm ci --prefix web
npm run dev --prefix web
```

Open <http://127.0.0.1:5174>. Vite proxies `/api` to
`http://127.0.0.1:4317`; the Python app permits only the two documented local
Vite origins. Keep the API path relative in frontend code so both development
and packaged builds use the same client.

## Routes and source layout

```text
src/
├── App.tsx                  route table and shared providers
├── pages.tsx                page implementations
├── components/app-shell.tsx navigation and responsive shell
├── components/ui/           shadcn-style reusable primitives
├── hooks/use-api.ts         polling/query hook
├── lib/api.ts               fetch helper and shared API types
├── index.css                Tailwind theme and global tokens
└── test/setup.ts            Vitest DOM setup
```

Current client routes:

| Route | Purpose |
| --- | --- |
| `/` | Hub health and recent lifecycle operations. |
| `/catalog` | Games, packs, tasks, profiles, and model-run launch. |
| `/auth` | Provider sessions and Steam QR login. |
| `/runtimes` | Runtime doctor, prepare, verify, and prune. |
| `/runs` | Run history. |
| `/reports` | Aggregate result view. |
| `/settings` | Local Rhenium settings. |

`pages.tsx` is intentionally consolidated while the UI is small. Split a page
into its own module when it gains independent state, tests, or reusable sections;
do not add another parallel component system.

## shadcn conventions

UI primitives live in `src/components/ui` and use Tailwind theme tokens,
`class-variance-authority`, and the shared `cn()` helper. When adding a shadcn
component:

- keep the generated primitive in `components/ui` and application composition
  outside that directory;
- preserve keyboard behavior and accessible labels from the upstream primitive;
- use semantic tokens such as `bg-background` and `text-muted-foreground`, not
  hard-coded light/dark colors;
- use Sonner for transient success/failure feedback and `Alert` for persistent
  page errors;
- reuse `StatusBadge`, `ErrorAlert`, and polling behavior before creating a new
  status vocabulary;
- verify narrow and wide layouts because the shared shell has a responsive
  sidebar/sheet navigation.

The repository owns the checked-in component source. Adding or updating a
component must be reviewed like any other code change; a generator output is not
automatically accepted.

## API and long-running operations

The UI uses the same `/api` routes documented in
[Managed authentication and runtimes](../docs/managed-runtimes.md#management-api).
Use the generic `api<T>()` helper for mutations and `useApi<T>()` for read/poll
views.

Login, runtime preparation, verification, and pruning are
asynchronous operations. A mutation returns an operation record; clients poll
`/api/operations/{id}` or the operations list until it reaches a terminal state.

Important states:

- `waiting_user`: display `publicState.challenge`; Steam uses its `uri` to render
  a QR code with `qrcode.react`.
- `running`: show `progress` and `phase` without assuming progress is monotonic
  across nested tools.
- `action_required`: display `publicState.action` and let the operator complete
  the legitimate external step before retrying.
- `completed`: refresh provider/runtime data from its authoritative GET
  route rather than guessing the new state.
- `failed`: show the server error without exposing stack traces or local secrets.

Never add `AuthSession.secret`, Steam refresh tokens, credentials, or full local
state records to frontend types, logs, error toasts, or browser storage. The Web
UI is local-only but is not a secret-management boundary.

## Tests and build

```sh
npm run lint --prefix web
npm run test --prefix web
npm run build --prefix web
```

The production build runs TypeScript project checks before Vite. Test user-visible
behavior with Testing Library and Vitest rather than asserting Tailwind class
strings. Mock the HTTP boundary; frontend tests must never trigger Steam or Docker.

The Rhenium wheel force-includes `web/dist` as `rhenium/web_dist`. Keep
`web/dist/.keep` so editable/core installation succeeds before the frontend is
built, but always run the production build before creating a release wheel. A
release check should inspect the wheel and confirm that `index.html` plus hashed
assets are present.

## Security boundary

`rhenium web` binds only to loopback, and mutating auth/runtime API routes
perform an additional loopback-client check. Do not relax either control merely
to access the UI from another machine. Use the CLI directly on the runtime host
or implement an authenticated remote control plane as a separate reviewed design.

The UI intentionally has no analytics, CDN assets, third-party API calls, or
credential persistence. Runtime preparation may use Steam/GitHub networking on
the host, but evaluation artifacts run under their game plugin's network policy.
