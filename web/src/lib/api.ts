export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export type Operation = {
  id: string
  kind: string
  target: string
  status: string
  phase: string
  progress: number
  publicState: {
    challenge?: { kind: string; uri: string; expires_at?: string; message?: string }
    action?: { kind: string; message: string; details?: Record<string, unknown> }
  }
  result: Record<string, unknown>
  error?: string
}

export type Runtime = {
  key: string
  gameId: string
  id: string
  name: string
  version: string
  provider: string
  restricted: boolean
  hostPlatforms: string[]
  hostPlatform: string
  hostSupported: boolean
  status: string
  ready: boolean
  error?: string
}
