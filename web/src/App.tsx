import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/components/app-shell'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Toaster } from '@/components/ui/sonner'
import {
  AuthPage,
  CatalogPage,
  OverviewPage,
  RuntimePage,
  RunsPage,
  SettingsPage,
} from '@/pages'

export default function App() {
  return (
    <BrowserRouter>
      <TooltipProvider>
        <AppShell>
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/catalog" element={<CatalogPage />} />
            <Route path="/auth" element={<AuthPage />} />
            <Route path="/runtimes" element={<RuntimePage />} />
            <Route path="/runs" element={<RunsPage />} />
            <Route path="/reports" element={<RunsPage reports />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </AppShell>
        <Toaster richColors />
      </TooltipProvider>
    </BrowserRouter>
  )
}

