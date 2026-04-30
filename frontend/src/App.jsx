import { Component } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { UserProvider, useUser } from './context/UserContext'
import { ThemeProvider } from './context/ThemeContext'
import Navbar from './components/shared/Navbar'
import Onboarding from './pages/Onboarding'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Session from './pages/Session'
import Progress from './pages/Progress'
import Practice from './pages/Practice'
import SessionHistory from './pages/SessionHistory'
import Profile from './pages/Profile'

// ── Error Boundary ─────────────────────────────────────────────────────────────
// Catches render errors that would otherwise show a completely blank page.
class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('[nib.ai] Render error:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', minHeight: '100vh', gap: '1rem',
          padding: '2rem', textAlign: 'center',
        }}>
          <h2 style={{ color: 'var(--amber, #e8a838)' }}>Something went wrong</h2>
          <p style={{ color: 'var(--text-muted, #888)', maxWidth: 420, fontSize: '0.9rem' }}>
            {this.state.error.message}
          </p>
          <button
            style={{
              padding: '0.5rem 1.25rem', borderRadius: 8, border: 'none',
              background: 'var(--amber, #e8a838)', color: '#000', cursor: 'pointer',
              fontWeight: 600,
            }}
            onClick={() => {
              this.setState({ error: null })
              window.location.href = '/dashboard'
            }}
          >
            Go to dashboard
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

// ── Route helpers ──────────────────────────────────────────────────────────────

function ProtectedRoute({ children }) {
  const { profile } = useUser()
  if (!profile) return <Navigate to="/" replace />
  return children
}

function WithNav({ children }) {
  return (
    <>
      <Navbar />
      <main>{children}</main>
    </>
  )
}

function AppRoutes() {
  const { profile } = useUser()

  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route
          path="/"
          element={profile ? <Navigate to="/dashboard" replace /> : <Onboarding />}
        />
        <Route
          path="/login"
          element={profile ? <Navigate to="/dashboard" replace /> : <Login />}
        />

        {/* Protected pages */}
        <Route path="/dashboard" element={<ProtectedRoute><WithNav><Dashboard /></WithNav></ProtectedRoute>} />
        <Route path="/session"   element={<ProtectedRoute><WithNav><Session /></WithNav></ProtectedRoute>} />
        <Route path="/progress"  element={<ProtectedRoute><WithNav><Progress /></WithNav></ProtectedRoute>} />
        <Route path="/practice"  element={<ProtectedRoute><WithNav><Practice /></WithNav></ProtectedRoute>} />
        <Route path="/history"   element={<ProtectedRoute><WithNav><SessionHistory /></WithNav></ProtectedRoute>} />
        <Route path="/profile"   element={<ProtectedRoute><WithNav><Profile /></WithNav></ProtectedRoute>} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

// ── Root ───────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <UserProvider>
          <AppRoutes />
        </UserProvider>
      </ThemeProvider>
    </ErrorBoundary>
  )
}
