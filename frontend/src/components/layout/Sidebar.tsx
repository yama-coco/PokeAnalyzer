import { NavLink } from 'react-router-dom'
import {
  Swords,
  Gauge,
  Heart,
  Shield,
  Calculator,
  Users,
  Search,
  Monitor,
  Activity,
} from 'lucide-react'

const navItems = [
  { to: '/', icon: Swords, label: 'ダッシュボード' },
  { to: '/speed', icon: Gauge, label: '素早さ順位' },
  { to: '/hp', icon: Heart, label: 'HP追跡' },
  { to: '/protect', icon: Shield, label: 'まもる管理' },
  { to: '/damage', icon: Calculator, label: 'ダメージ計算' },
  { to: '/party', icon: Users, label: 'パーティ管理' },
  { to: '/meta', icon: Search, label: 'メタ型検索' },
  { to: '/hud-settings', icon: Monitor, label: 'OBS HUD' },
]

export function Sidebar() {
  return (
    <aside className="w-56 bg-gray-900 text-gray-300 flex flex-col border-r border-gray-800 shrink-0">
      <div className="px-4 py-4 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <Activity className="w-6 h-6 text-blue-400" />
          <h1 className="text-lg font-bold text-white tracking-tight">PAL-C</h1>
        </div>
        <p className="text-[10px] text-gray-500 mt-0.5">PokeAnalysis Live</p>
      </div>
      <nav className="flex-1 py-2">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                isActive
                  ? 'bg-blue-600/20 text-blue-400 border-r-2 border-blue-400'
                  : 'hover:bg-gray-800 hover:text-white'
              }`
            }
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
        Phase 4 • v0.4.0
      </div>
    </aside>
  )
}
