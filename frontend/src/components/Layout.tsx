import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import clsx from 'clsx'

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: '◈' },
  { path: '/runs/new', label: 'New Run', icon: '⊕' },
  { path: '/compare', label: 'Compare', icon: '⇄' },
]

const adminItems = [
  { path: '/admin', label: 'Admin', icon: '⚙' },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link to="/dashboard" className="flex items-center space-x-2">
                <span className="text-2xl font-bold text-proteus-700">Proteus</span>
                <span className="text-xs bg-proteus-100 text-proteus-800 px-2 py-0.5 rounded-full font-medium">
                  v1.0
                </span>
              </Link>
              <div className="ml-10 flex items-center space-x-4">
                {navItems.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={clsx(
                      'flex items-center space-x-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                      location.pathname === item.path
                        ? 'bg-proteus-50 text-proteus-700'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                    )}
                  >
                    <span>{item.icon}</span>
                    <span>{item.label}</span>
                  </Link>
                ))}
                {(user?.role === 'admin' || user?.role === 'mentor') &&
                  adminItems.map((item) => (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={clsx(
                        'flex items-center space-x-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                        location.pathname === item.path
                          ? 'bg-proteus-50 text-proteus-700'
                          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                      )}
                    >
                      <span>{item.icon}</span>
                      <span>{item.label}</span>
                    </Link>
                  ))}
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <Link
                to="/profile"
                className="flex items-center space-x-2 text-sm text-gray-600 hover:text-gray-900"
              >
                <div className="w-8 h-8 rounded-full bg-proteus-100 flex items-center justify-center">
                  <span className="text-proteus-700 font-medium text-sm">
                    {user?.full_name?.charAt(0) || '?'}
                  </span>
                </div>
                <span className="hidden sm:block">{user?.full_name}</span>
              </Link>
              <button
                onClick={handleLogout}
                className="text-sm text-gray-500 hover:text-red-600 transition-colors"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">{children}</main>
    </div>
  )
}
