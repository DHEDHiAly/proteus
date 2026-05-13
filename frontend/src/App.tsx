import { Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import { useAuth } from './hooks/useAuth'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import NewRunPage from './pages/NewRunPage'
import RunDetailPage from './pages/RunDetailPage'
import ComparePage from './pages/ComparePage'
import ProfilePage from './pages/ProfilePage'
import AdminPage from './pages/AdminPage'
import AgentPage from './pages/AgentPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (user?.role !== 'admin' && user?.role !== 'mentor') {
    return <Navigate to="/dashboard" replace />
  }
  return <>{children}</>
}

export default function App() {
  const { loadUser, isAuthenticated } = useAuth()

  useEffect(() => {
    if (isAuthenticated) {
      loadUser()
    }
  }, [isAuthenticated, loadUser])

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Layout>
              <DashboardPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/runs/new"
        element={
          <ProtectedRoute>
            <Layout>
              <NewRunPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/runs/:id"
        element={
          <ProtectedRoute>
            <Layout>
              <RunDetailPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/compare"
        element={
          <ProtectedRoute>
            <Layout>
              <ComparePage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <Layout>
              <ProfilePage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <AdminRoute>
            <Layout>
              <AdminPage />
            </Layout>
          </AdminRoute>
        }
      />
      <Route
        path="/agent"
        element={
          <ProtectedRoute>
            <Layout>
              <AgentPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route path="/" element={<Navigate to="/agent" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
