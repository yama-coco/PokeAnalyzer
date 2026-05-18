import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useBattleState } from '../../hooks/useBattleState'
import { useWebSocket } from '../../hooks/useWebSocket'
import { BattleContext } from '../../contexts/BattleContext'
import { useEffect } from 'react'

export function Layout() {
  const battle = useBattleState()
  const { isConnected } = useWebSocket({
    url: '/api/vision/ws',
    onMessage: () => {
      battle.refreshState()
    },
  })

  useEffect(() => {
    battle.refreshState()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <BattleContext.Provider value={{ ...battle, wsConnected: isConnected }}>
      <div className="flex h-screen bg-gray-950 text-gray-100">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header
            phase={battle.matchState?.phase || 'none'}
            turn={battle.matchState?.turn || 0}
            isConnected={isConnected}
          />
          <main className="flex-1 overflow-y-auto p-4">
            <Outlet />
          </main>
        </div>
      </div>
    </BattleContext.Provider>
  )
}
