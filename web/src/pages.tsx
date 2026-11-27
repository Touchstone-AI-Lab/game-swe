import {
  AlertCircle,
  CheckCircle2,
  CircleDashed,
  Download,
  ExternalLink,
  KeyRound,
  Play,
  RefreshCcw,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApi } from "@/hooks/use-api";
import { api, type Operation, type Runtime } from "@/lib/api";

type Dictionary = Record<string, unknown>;

function PageHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <header className="mb-6">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
        {title}
      </h1>
      <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
        {description}
      </p>
    </header>
  );
}

function ErrorAlert({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <Alert variant="destructive" className="mb-4">
      <AlertCircle />
      <AlertTitle>Request failed</AlertTitle>
      <AlertDescription className="break-all">{message}</AlertDescription>
    </Alert>
  );
}

function StatusBadge({ value }: { value: string }) {
  const positive = ["ready", "passed", "completed", "running"].includes(value);
  return (
    <Badge
      variant={
        positive ? "default" : value === "missing" ? "secondary" : "outline"
      }
    >
      {value}
    </Badge>
  );
}

export function OverviewPage() {
  const health = useApi<Dictionary>("/api/health", 5000);
  const operations = useApi<{ operations: Operation[] }>(
    "/api/operations?limit=6",
    2000,
  );
  const stats = [
    ["Plugins", health.data?.pluginCount],
    ["Auth providers", health.data?.authProviderCount],
    ["Packs", health.data?.packCount],
    ["Tasks", health.data?.taskCount],
  ];
  return (
    <>
      <PageHeader
        title="Overview"
        description="Local health, licensed runtime readiness, and current operations."
      />
      <ErrorAlert message={health.error} />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map(([label, value]) => (
          <Card key={String(label)}>
            <CardHeader className="pb-2">
              <CardDescription>{String(label)}</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold">{String(value ?? "—")}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_1.35fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {health.data?.degraded ? (
                <ShieldAlert className="size-5 text-amber-500" />
              ) : (
                <CheckCircle2 className="size-5 text-emerald-500" />
              )}
              Hub health
            </CardTitle>
            <CardDescription>
              Version {String(health.data?.version ?? "—")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <StatusBadge
              value={health.data?.degraded ? "degraded" : "healthy"}
            />
            <p className="mt-4 text-sm text-muted-foreground">
              Missing licensed runtimes are isolated degradations and do not
              prevent catalog access.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recent operations</CardTitle>
            <CardDescription>
              Authentication and runtime lifecycle activity.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {(operations.data?.operations ?? []).map((item) => (
              <div key={item.id} className="space-y-2">
                <div className="flex items-center justify-between gap-3 text-sm">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{item.target}</p>
                    <p className="truncate text-muted-foreground">
                      {item.phase}
                    </p>
                  </div>
                  <StatusBadge value={item.status} />
                </div>
                <Progress value={item.progress} />
              </div>
            ))}
            {!operations.data?.operations?.length && (
              <p className="text-sm text-muted-foreground">
                No lifecycle operations yet.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

export function CatalogPage() {
  const games = useApi<{ games: Dictionary[] }>("/api/games");
  const packs = useApi<{ packs: Dictionary[] }>("/api/packs");
  const tasks = useApi<{ tasks: Dictionary[] }>("/api/tasks");
  const [running, setRunning] = useState<string>();
  async function runTask(task: Dictionary) {
    const key = String(task.key);
    const [game, pack, id] = key.split("/");
    setRunning(key);
    try {
      await api(`/api/games/${game}/packs/${pack}/tasks/${id}/runs`, {
        method: "POST",
      });
      toast.success("Run queued");
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRunning(undefined);
    }
  }
  return (
    <>
      <PageHeader
        title="Catalog"
        description="Installed game plugins, benchmark packs, tasks, and evaluation profiles."
      />
      <ErrorAlert message={games.error ?? tasks.error ?? packs.error} />
      <Tabs defaultValue="tasks">
        <TabsList>
          <TabsTrigger value="tasks">Tasks</TabsTrigger>
          <TabsTrigger value="games">Games</TabsTrigger>
          <TabsTrigger value="packs">Packs</TabsTrigger>
        </TabsList>
        <TabsContent value="tasks">
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Task</TableHead>
                  <TableHead>Game / Pack</TableHead>
                  <TableHead>Difficulty</TableHead>
                  <TableHead>Profiles</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {(tasks.data?.tasks ?? []).map((task) => (
                  <TableRow key={String(task.key)}>
                    <TableCell>
                      <p className="font-medium">{String(task.title)}</p>
                      <p className="max-w-xl text-xs text-muted-foreground">
                        {String(task.summary)}
                      </p>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {String(task.gameId)}/{String(task.packId)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">
                        {String(task.difficulty)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {Array.isArray(task.profiles)
                        ? task.profiles.map((profile) => (
                            <Badge
                              key={String((profile as Dictionary).id)}
                              variant="outline"
                              className="mr-1"
                            >
                              {String((profile as Dictionary).id)}
                            </Badge>
                          ))
                        : null}
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        onClick={() => void runTask(task)}
                        disabled={running === task.key}
                      >
                        <Play />
                        Run model
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>
        <TabsContent value="games">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {(games.data?.games ?? []).map((game) => (
              <Card key={String(game.id)}>
                <CardHeader>
                  <CardTitle>{String(game.name)}</CardTitle>
                  <CardDescription>{String(game.game_id)}</CardDescription>
                </CardHeader>
                <CardContent>
                  <Badge>{String(game.version)}</Badge>
                  <p className="mt-3 text-sm text-muted-foreground">
                    {String(game.taskCount)} tasks
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
        <TabsContent value="packs">
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Pack</TableHead>
                  <TableHead>Catalog</TableHead>
                  <TableHead>Tasks</TableHead>
                  <TableHead>Runtime</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(packs.data?.packs ?? []).map((pack) => (
                  <TableRow key={String(pack.key)}>
                    <TableCell className="font-mono">
                      {String(pack.key)}
                    </TableCell>
                    <TableCell>{String(pack.catalog)}</TableCell>
                    <TableCell>{String(pack.taskCount)}</TableCell>
                    <TableCell>
                      <StatusBadge
                        value={
                          (pack.runtime as Dictionary)?.available
                            ? "ready"
                            : "missing"
                        }
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>
      </Tabs>
    </>
  );
}

export function AuthPage() {
  const providers = useApi<{ providers: Dictionary[] }>(
    "/api/auth/providers",
    3000,
  );
  const [operationId, setOperationId] = useState<string>();
  const operation = useApi<Operation>(
    operationId
      ? `/api/operations/${operationId}`
      : "/api/operations/not-selected",
    1000,
  );
  const selected = operationId ? operation.data : undefined;
  useEffect(() => {
    if (selected?.status === "completed") void providers.refresh();
  }, [selected?.status, providers.refresh]);
  async function login(provider: string) {
    try {
      const result = await api<Operation>(
        `/api/auth/providers/${provider}/login`,
        { method: "POST", body: JSON.stringify({ account: "default" }) },
      );
      setOperationId(result.id);
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : String(reason));
    }
  }
  async function logout(provider: string, alias: string) {
    await api(`/api/auth/providers/${provider}/sessions/${alias}`, {
      method: "DELETE",
    });
    toast.success("Local session deleted");
    await providers.refresh();
  }
  return (
    <>
      <PageHeader
        title="Authentication"
        description="Provider-owned QR login with sessions stored only in the local Rhenium database."
      />
      <Alert className="mb-6">
        <ShieldAlert />
        <AlertTitle>Local secret boundary</AlertTitle>
        <AlertDescription>
          Steam refresh tokens are stored in plaintext SQLite by configured
          policy. Never share or upload the Rhenium state directory.
        </AlertDescription>
      </Alert>
      <ErrorAlert message={providers.error} />
      <div className="grid gap-4 lg:grid-cols-2">
        {(providers.data?.providers ?? []).map((provider) => (
          <Card key={String(provider.id)}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <KeyRound className="size-5" />
                {String(provider.name)}
              </CardTitle>
              <CardDescription>
                {String(provider.id)} provider · {String(provider.version)}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {(Array.isArray(provider.sessions) ? provider.sessions : []).map(
                (session) => {
                  const item = session as Dictionary;
                  return (
                    <div
                      key={String(item.accountAlias)}
                      className="flex items-center justify-between rounded-md border p-3"
                    >
                      <div>
                        <p className="font-medium">{String(item.principal)}</p>
                        <p className="text-xs text-muted-foreground">
                          alias: {String(item.accountAlias)}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge value={String(item.status)} />
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          onClick={() =>
                            void logout(
                              String(provider.id),
                              String(item.accountAlias),
                            )
                          }
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    </div>
                  );
                },
              )}
              <Button onClick={() => void login(String(provider.id))}>
                <KeyRound />
                Login with QR
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
      <Dialog
        open={Boolean(operationId && selected?.status !== "completed")}
        onOpenChange={(open) => !open && setOperationId(undefined)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Steam login</DialogTitle>
            <DialogDescription>
              {selected?.phase ?? "Connecting to Steam…"}
            </DialogDescription>
          </DialogHeader>
          <div className="grid place-items-center gap-4 py-4">
            {selected?.publicState.challenge?.uri ? (
              <div className="rounded-xl bg-white p-4">
                <QRCodeSVG
                  value={selected.publicState.challenge.uri}
                  size={240}
                />
              </div>
            ) : (
              <CircleDashed className="size-12 animate-spin text-muted-foreground" />
            )}
            <Progress value={selected?.progress ?? 5} className="w-full" />
            {selected?.error && (
              <p className="text-sm text-destructive">{selected.error}</p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function RuntimePage() {
  const runtimes = useApi<{ runtimes: Runtime[] }>("/api/runtimes", 3000);
  const operations = useApi<{ operations: Operation[] }>(
    "/api/operations?limit=20",
    1500,
  );
  async function mutate(item: Runtime, action: "prepare" | "verify" | "prune") {
    const method = action === "prune" ? "DELETE" : "POST";
    const suffix = action === "prune" ? "" : `/${action}`;
    try {
      await api(`/api/runtimes/${item.gameId}/${item.id}${suffix}`, {
        method,
        body:
          action === "prepare"
            ? JSON.stringify({ account: "default" })
            : undefined,
      });
      toast.success(`${action} started`);
      await operations.refresh();
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : String(reason));
    }
  }
  const active = useMemo(
    () =>
      new Map(
        (operations.data?.operations ?? []).map((item) => [item.target, item]),
      ),
    [operations.data],
  );
  return (
    <>
      <PageHeader
        title="Runtimes"
        description="Explicitly acquire, build, verify, and prune non-redistributable evaluator runtimes."
      />
      <ErrorAlert message={runtimes.error} />
      <div className="space-y-4">
        {(runtimes.data?.runtimes ?? []).map((item) => {
          const op = active.get(item.key);
          return (
            <Card key={item.key}>
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <CardTitle>{item.name}</CardTitle>
                    <CardDescription className="mt-1 font-mono">
                      {item.key}
                    </CardDescription>
                  </div>
                  <StatusBadge value={item.status} />
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {item.hostPlatforms.map((host) => (
                    <Badge key={host} variant="outline">
                      {host}
                    </Badge>
                  ))}
                </div>
                {op &&
                  ["queued", "running", "action_required"].includes(
                    op.status,
                  ) && (
                    <div className="mt-4 space-y-2">
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{op.phase}</span>
                        <span>{op.progress}%</span>
                      </div>
                      <Progress value={op.progress} />
                      {op.publicState.action && (
                        <Alert>
                          <ExternalLink />
                          <AlertTitle>{op.publicState.action.kind}</AlertTitle>
                          <AlertDescription>{op.publicState.action.message}</AlertDescription>
                        </Alert>
                      )}
                    </div>
                  )}
                <div className="mt-5 flex flex-wrap gap-2">
                <Button
                  onClick={() => void mutate(item, "prepare")}
                  disabled={!item.hostSupported}
                >
                    <Download />
                    Prepare
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => void mutate(item, "verify")}
                  >
                    <RefreshCcw />
                    Verify
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={() => void mutate(item, "prune")}
                  >
                    <Trash2 />
                    Prune
                  </Button>
                </div>
                {item.error && (
                  <p className="mt-3 text-sm text-destructive">{item.error}</p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </>
  );
}

export function RunsPage({ reports = false }: { reports?: boolean }) {
  const values = useApi<Dictionary>(
    reports ? "/api/reports" : "/api/runs",
    3000,
  );
  const rows = reports
    ? []
    : ((values.data?.runs as Dictionary[] | undefined) ?? []);
  return (
    <>
      <PageHeader
        title={reports ? "Reports" : "Runs"}
        description={
          reports
            ? "Aggregate benchmark outcomes across games and packs."
            : "Evaluation history and normalized outcomes."
        }
      />
      <ErrorAlert message={values.error} />
      {reports ? (
        <Card>
          <CardContent className="pt-6">
            <pre className="overflow-auto text-xs">
              {JSON.stringify(values.data ?? {}, null, 2)}
            </pre>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run</TableHead>
                <TableHead>Task</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Phase</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((run) => (
                <TableRow key={String(run.id)}>
                  <TableCell className="font-mono text-xs">
                    {String(run.id)}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {String(run.taskKey)}
                  </TableCell>
                  <TableCell>
                    <StatusBadge value={String(run.status)} />
                  </TableCell>
                  <TableCell>{String(run.score)}</TableCell>
                  <TableCell>{String(run.phase)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </>
  );
}

export function SettingsPage() {
  const settings = useApi<Dictionary>("/api/settings");
  const [form, setForm] = useState({
    modelName: "",
    modelBaseUrl: "",
    modelApiKey: "",
  });
  useEffect(() => {
    if (settings.data)
      setForm((current) => ({
        ...current,
        modelName: String(settings.data?.modelName ?? ""),
        modelBaseUrl: String(settings.data?.modelBaseUrl ?? ""),
      }));
  }, [settings.data]);
  async function save() {
    try {
      await api("/api/settings", {
        method: "PATCH",
        body: JSON.stringify({ values: form }),
      });
      toast.success("Settings saved");
      setForm((current) => ({ ...current, modelApiKey: "" }));
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : String(reason));
    }
  }
  return (
    <>
      <PageHeader
        title="Settings"
        description="Local model-under-test configuration. Provider tokens are managed separately."
      />
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Model</CardTitle>
          <CardDescription>
            Configure the endpoint used by run-model and the Hub UI.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="model-name">Model name</Label>
            <Input
              id="model-name"
              value={form.modelName}
              onChange={(event) =>
                setForm({ ...form, modelName: event.target.value })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="base-url">Base URL</Label>
            <Input
              id="base-url"
              value={form.modelBaseUrl}
              onChange={(event) =>
                setForm({ ...form, modelBaseUrl: event.target.value })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="api-key">API key</Label>
            <Input
              id="api-key"
              type="password"
              placeholder={
                settings.data?.modelApiKeyConfigured
                  ? "Configured — enter to replace"
                  : "Not configured"
              }
              value={form.modelApiKey}
              onChange={(event) =>
                setForm({ ...form, modelApiKey: event.target.value })
              }
            />
          </div>
          <Button onClick={() => void save()}>Save settings</Button>
        </CardContent>
      </Card>
    </>
  );
}

export function LoadingPage() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-56" />
      <Skeleton className="h-48 w-full" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}
