import { render, screen } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'

import App from './App'

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const value = String(input)
      const body = value.includes('/api/health')
        ? { version: '0.6.0', pluginCount: 3, authProviderCount: 1, packCount: 3, taskCount: 12, degraded: false }
        : value.includes('/api/operations')
          ? { operations: [] }
          : {}
      return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }),
  )
})

test('renders the complete Hub navigation and health overview', async () => {
  render(<App />)
  expect(await screen.findByText('Hub health')).toBeInTheDocument()
  expect(screen.getByText('Authentication')).toBeInTheDocument()
  expect(screen.getByText('Runtimes')).toBeInTheDocument()
  expect(screen.queryByText('Workers')).not.toBeInTheDocument()
  expect(screen.getByText(/Version 0\.6\.0/)).toBeInTheDocument()
})
