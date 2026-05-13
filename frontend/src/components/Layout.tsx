import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import clsx from 'clsx'

const navItems = [
  { path: '/agent', label: 'Workspace', icon: 'P' },
  { path: '/dashboard', label: 'History', icon: '◈' },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <div className="min-h-screen bg-black text-white">
      <nav className="border-b border-[#1a1a1a]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-12 items-center">
            <div className="flex items-center space-x-6">
              <Link to="/agent" className="flex items-center space-x-2">
                <div className="w-7 h-7 border border-white/30 rounded flex items-center justify-center">
                  <span className="text-xs font-bold">P</span>
                </div>
                <span className="text-sm font-bold tracking-tight">Proteus</span>
              </Link>
              <div className="flex items-center space-x-1">
                {navItems.map((item) => (
                  <Link key={item.path} to={item.path}
                    className={clsx(
                      'px-3 py-1.5 rounded text-[11px] font-medium transition-colors',
                      location.pathname === item.path
                        ? 'bg-white/10 text-white'
                        : 'text-gray-500 hover:text-white hover:bg-white/5'
                    )}>
                    {item.label}
                  </Link>
                ))}
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <Link to="/profile" className="text-[11px] text-gray-500 hover:text-white transition-colors">
                {user?.full_name}
              </Link>
              <button onClick={handleLogout}
                className="text-[11px] text-gray-600 hover:text-white transition-colors">
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">{children}</main>
    </div>
  )
}
