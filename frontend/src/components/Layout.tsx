import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import clsx from 'clsx'

const navItems = [
  { path: '/agent', label: 'Workspace', icon: 'WS' },
  { path: '/benchmarks', label: 'Benchmarks', icon: 'BM' },
  { path: '/dashboard', label: 'History', icon: 'HI' },
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
              <Link to="/agent" className="flex items-center space-x-2 group">
                <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 group-hover:opacity-80 transition-opacity">
                  <defs><linearGradient id="nl" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stop-color="#fff"/><stop offset="50%" stop-color="#666"/><stop offset="100%" stop-color="#fff"/>
                  </linearGradient></defs>
                  <g stroke="url(#nl)" strokeWidth="2.5" strokeLinecap="round" fill="none">
                    <path d="M30 15 Q50 25 70 15 Q50 5 30 15" opacity=".9"/>
                    <path d="M30 35 Q50 45 70 35 Q50 25 30 35" opacity=".7"/>
                    <path d="M30 55 Q50 65 70 55 Q50 45 30 55" opacity=".5"/>
                    <path d="M30 75 Q50 85 70 75 Q50 65 30 75" opacity=".3"/>
                    <line x1="30" y1="15" x2="30" y2="75" opacity=".6"/>
                    <line x1="70" y1="15" x2="70" y2="75" opacity=".6"/>
                  </g>
                </svg>
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
