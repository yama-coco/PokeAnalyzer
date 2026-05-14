import { useContext } from 'react'
import { BattleContext } from '../../contexts/BattleContext'
import type { SpeedEntry } from '../../types/battle'
import { Zap, Wind, RotateCcw } from 'lucide-react'

function SpeedRow({ entry }: { entry: SpeedEntry }) {
  const isAlly = entry.side === 'ally'
  return (
    <div className={`flex items-center gap-3 px-3 py-2 rounded-lg ${
      isAlly ? 'bg-blue-950/40 border border-blue-800/30' : 'bg-red-950/40 border border-red-800/30'
    }`}>
      <span className="w-6 h-6 flex items-center justify-center rounded-full bg-gray-800 text-xs font-bold">
        {entry.order}
      </span>
      <div className="flex-1">
        <span className={`font-medium text-sm ${isAlly ? 'text-blue-300' : 'text-red-300'}`}>
          {entry.name}
        </span>
        <span className="text-xs text-gray-500 ml-2">
          (S{entry.base_speed})
        </span>
      </div>
      <div className="text-right">
        <span className="font-mono text-sm text-white">
          {entry.effective_speed}
        </span>
      </div>
    </div>
  )
}

export function SpeedTierPanel() {
  const battle = useContext(BattleContext)
  if (!battle) return null

  const { speedOrder, matchState } = battle
  const entries = speedOrder?.speed_order || []
  const trickRoom = speedOrder?.trick_room || false
  const tailwindAlly = matchState?.field_state.tailwind_ally || false
  const tailwindEnemy = matchState?.field_state.tailwind_enemy || false

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
          <Zap className="w-4 h-4 text-yellow-400" />
          素早さ順位
        </h2>
        <div className="flex gap-1.5">
          {tailwindAlly && (
            <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-blue-900 text-blue-300">
              <Wind className="w-3 h-3" /> 味方追い風
            </span>
          )}
          {tailwindEnemy && (
            <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-red-900 text-red-300">
              <Wind className="w-3 h-3" /> 相手追い風
            </span>
          )}
          {trickRoom && (
            <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-purple-900 text-purple-300">
              <RotateCcw className="w-3 h-3" /> トリル
            </span>
          )}
        </div>
      </div>
      <div className="space-y-1.5">
        {entries.length > 0 ? (
          entries.map((entry: SpeedEntry) => (
            <SpeedRow key={entry.slot} entry={entry} />
          ))
        ) : (
          <p className="text-xs text-gray-600 text-center py-4">
            バトル開始後に表示されます
          </p>
        )}
      </div>
    </div>
  )
}
