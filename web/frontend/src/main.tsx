import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { AuthProvider } from '@/lib/auth'
import { ToastProvider } from '@/components/Toaster'
import { ThemeProvider } from '@/lib/theme'
import { BootstrapProvider } from './lib/bootstrap-context.tsx'
import './index.css'
import '@/i18n'
import App from './App.tsx'

// data router (e não <BrowserRouter>) para o useBlocker funcionar; as rotas continuam
// declaradas com <Routes> no App, abaixo desta rota coringa
const router = createBrowserRouter([
  {
    path: '*',
    element: (
      <ToastProvider>
        <AuthProvider>
          <BootstrapProvider>
            <App />
          </BootstrapProvider>
        </AuthProvider>
      </ToastProvider>
    ),
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
  </StrictMode>,
)