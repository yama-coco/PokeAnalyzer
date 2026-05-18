import { useEffect, useState } from 'react'
import { battleApi } from '../../api/battle'
import type { MatchState, SpeedOrderResponse } from '../../types/battle'

export function HUDOverlay() {
  const [matchState, setMatchState] = useState<MatchState | null>(null)
  const [speedOrder, setSpeedOrder] = useState<SpeedOrderResponse | null>(null)
  const [protectStates, setProtectStates] = useState<Record<string, { next_success_rate: number }>>({})

  useEffect(() => {
    let cancelled = false

    const refresh = async () => {
      try {
        const [state, speed, protect] = await Promise.all([
          battleApi.getState(),
          battleApi.getSpeedOrder(),
          battleApi.getProtectState(),
        ])
        if (!cancelled) {
          setMatchState(state)
          setSpeedOrder(speed)
          setProtectStates(protect)
        }
      } catch {
        // ignore
      }
    }

    refresh()
    const interval = setInterval(refresh, 1500)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  const phase = matchState?.phase || 'none'
  if (phase !== 'in_battle') return null

  const entries = speedOrder?.speed_order || []
  const trickRoom = speedOrder?.trick_room || false
  const field = matchState?.field_state

  return (
    <div className="fixed inset-0 pointer-events-none font-sans text-white">
      {/* 素早さ順位 - 左上 */}
      <div className="absolute top-2 left-2 bg-black/60 backdrop-blur-sm rounded-lg p-2 min-w-[180px]">
        <div className="text-[10px] text-gray-400 mb-1 flex items-center gap-1">
          ⚡ 素早さ順
          {trickRoom && <span className="text-purple-400 ml-1">🔄TR</span>}
          {field?.tailwind_ally && <span className="text-blue-400 ml-1">💨味</span>}
          {field?.tailwind_enemy && <span className="text-red-400 ml-1">💨相</span>}
        </div>
        {entries.map(entry => (
          <div
            key={entry.slot}
            className={`flex items-center gap-2 py-0.5 text-xs ${
              entry.side === 'ally' ? 'text-blue-300' : 'text-red-300'
            }`}
          >
            <span className="w-4 text-center font-bold text-gray-400">{entry.order}</span>
            <span className="flex-1">{entry.name}</span>
            <span className="font-mono text-gray-300">{entry.effective_speed}</span>
          </div>
        ))}
      </div>

      {/* まもる確率 - 右上 */}
      {Object.keys(protectStates).length > 0 && (
        <div className="absolute top-2 right-2 bg-black/60 backdrop-blur-sm rounded-lg p-2 min-w-[140px]">
          <div className="text-[10px] text-gray-400 mb-1">🛡️ まもる確率</div>
          {Object.entries(protectStates).map(([name, state]) => (
            <div key={name} className="flex items-center justify-between py-0.5 text-xs">
              <span className="text-gray-300">{name}</span>
              <span className={`font-mono font-bold ${
                state.next_success_rate <= 11.2 ? 'text-red-400' :
                state.next_success_rate <= 33.4 ? 'text-yellow-400' : 'text-green-400'
              }`}>
                {state.next_success_rate}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ターン数 - 中央上 */}
      <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-black/60 backdrop-blur-sm rounded-full px-3 py-0.5">
        <span className="text-xs text-gray-400">T</span>
        <span className="text-sm font-bold font-mono ml-0.5">{matchState?.turn || 0}</span>
      </div>

      {/* フィールド状態 - 下部中央 */}
      {field && (field.weather !== 'none' || field.terrain) && (
        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5">
          {field.weather !== 'none' && (
            <span className="bg-black/60 backdrop-blur-sm rounded px-2 py-0.5 text-[10px]">
              {field.weather === 'sun' && '☀️ 晴れ'}
              {field.weather === 'rain' && '🌧️ 雨'}
              {field.weather === 'sand' && '⛰️ 砂嵐'}
              {field.weather === 'snow' && '❄️ 雪'}
            </span>
          )}
          {field.terrain && (
            <span className="bg-black/60 backdrop-blur-sm rounded px-2 py-0.5 text-[10px]">
              🌿 {field.terrain}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
