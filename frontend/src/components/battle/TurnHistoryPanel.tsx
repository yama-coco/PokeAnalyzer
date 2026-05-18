import { useEffect, useState } from 'react'
import { History } from 'lucide-react'
import { battleApi } from '../../api/battle'
import type { TurnLog } from '../../types/battle'

export function TurnHistoryPanel() {
  const [logs, setLogs] = useState<TurnLog[]>([])

  useEffect(() => {
    const fetch = async () => {
      try {
        const data = await battleApi.getAllLogs()
        setLogs(data)
      } catch {
        // ignore
      }
    }
    fetch()
    const interval = setInterval(fetch, 3000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2 mb-3">
        <History className="w-4 h-4 text-gray-400" />
        ターン履歴
      </h2>

      {logs.length > 0 ? (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {logs.map((log) => (
            <div key={log.turn} className="p-2 rounded bg-gray-800/50 border border-gray-700/50">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-gray-300">
                  ターン {log.turn}
                </span>
                <span className="text-[10px] text-gray-600">
                  {log.actions.length} アクション
                </span>
              </div>
              {log.actions.map((action, i) => (
                <div key={i} className="text-[11px] text-gray-400 pl-2">
                  <span className="text-gray-300">{action.pokemon_name}</span>
                  {' → '}
                  <span className="text-yellow-300">{action.action_name}</span>
                  {action.target_name && (
                    <span className="text-gray-500"> → {action.target_name}</span>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-gray-600 text-center py-4">
          ターン履歴なし
        </p>
      )}
    </div>
  )
}
