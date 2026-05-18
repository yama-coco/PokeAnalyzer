import { useEffect, useState } from 'react'
import { Shield } from 'lucide-react'
import { battleApi } from '../../api/battle'
import type { ProtectState } from '../../types/battle'

function ProtectCard({ state }: { state: ProtectState }) {
  const rate = state.next_success_rate
  let rateColor = 'text-green-400'
  if (rate <= 11.2) rateColor = 'text-red-400'
  else if (rate <= 33.4) rateColor = 'text-yellow-400'

  return (
    <div className="p-3 rounded-lg bg-gray-800/50 border border-gray-700">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-200">{state.name}</span>
        <span className={`text-lg font-bold font-mono ${rateColor}`}>
          {rate}%
        </span>
      </div>
      <div className="flex items-center gap-3 text-xs text-gray-500">
        <span>連続: {state.consecutive_uses}回</span>
        <span>通算: {state.total_uses}回</span>
        <span>成功: {state.total_successes}回</span>
      </div>
      {state.history.length > 0 && (
        <div className="mt-2 flex gap-1">
          {state.history.slice(-8).map((h, i) => (
            <span
              key={i}
              className={`w-5 h-5 rounded text-[10px] flex items-center justify-center ${
                h.success ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
              }`}
            >
              {h.turn}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export function ProtectPanel() {
  const [protectStates, setProtectStates] = useState<Record<string, ProtectState>>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetch = async () => {
      try {
        const states = await battleApi.getProtectState()
        setProtectStates(states)
        setError(null)
      } catch {
        setError('まもる状態の取得に失敗')
      }
    }
    fetch()
    const interval = setInterval(fetch, 3000)
    return () => clearInterval(interval)
  }, [])

  const entries = Object.values(protectStates)

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2 mb-3">
        <Shield className="w-4 h-4 text-cyan-400" />
        まもる管理
      </h2>

      {error && (
        <p className="text-xs text-red-400 mb-2">{error}</p>
      )}

      {entries.length > 0 ? (
        <div className="space-y-2">
          {entries.map((state) => (
            <ProtectCard key={state.name} state={state} />
          ))}
        </div>
      ) : (
        <p className="text-xs text-gray-600 text-center py-4">
          まもる使用履歴なし
        </p>
      )}

      <div className="mt-3 pt-3 border-t border-gray-800">
        <p className="text-[10px] text-gray-600">
          確率: 1回目 100% → 2回目 33.3% → 3回目 11.1% → 4回目 3.7%
        </p>
      </div>
    </div>
  )
}
