import {
  Boxes,
  ChartNoAxesCombined,
  Gamepad2,
  HeartPulse,
  KeyRound,
  PlayCircle,
  Settings,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'

const navigation = [
  ['/', 'Overview', HeartPulse],
  ['/catalog', 'Catalog', Gamepad2],
  ['/auth', 'Authentication', KeyRound],
  ['/runtimes', 'Runtimes', Boxes],
  ['/runs', 'Runs', PlayCircle],
  ['/reports', 'Reports', ChartNoAxesCombined],
  ['/settings', 'Settings', Settings],
] as const

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-svh bg-muted/30 lg:grid lg:grid-cols-[250px_1fr]">
      <aside className="border-b bg-background px-4 py-3 lg:sticky lg:top-0 lg:h-svh lg:border-r lg:border-b-0 lg:px-3 lg:py-5">
        <div className="flex items-center gap-3 px-2">
          <div className="grid size-9 place-items-center rounded-lg bg-primary text-primary-foreground">
            <span className="font-mono text-sm font-bold">Rh</span>
          </div>
          <div>
            <p className="font-semibold leading-none">Rhenium Hub</p>
            <p className="mt-1 text-xs text-muted-foreground">Licensed runtime control plane</p>
          </div>
        </div>
        <Separator className="my-4 hidden lg:block" />
        <nav className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
          {navigation.map(([path, label, Icon]) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/'}
              className={({ isActive }) =>
                cn(
                  'flex shrink-0 items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent',
                  isActive && 'bg-accent font-medium text-accent-foreground',
                )
              }
            >
              <Icon className="size-4" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="min-w-0 p-4 sm:p-6 lg:p-8">{children}</main>
    </div>
  )
}
