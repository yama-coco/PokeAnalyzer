import { useContext } from 'react'
import { Heart } from 'lucide-react'
import { BattleContext } from '../contexts/BattleContext'
import { HPTrackerPanel } from '../components/battle/HPTrackerPanel'
import type { DamageEvent } from '../types/battle'

export function HPPage() {
  const battle = useContext(BattleContext)
  if (!battle) return null

  const { damageHistory } = battle

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold text-gray-200 flex items-center gap-2">
        <Heart className="w-5 h-5 text-red-400" />
        HP追跡・ダメージ履歴
      </h1>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-6">
          <HPTrackerPanel />
        </div>
        <div className="col-span-6">
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
            <h2 className="text-sm font-semibold text-gray-300 mb-3">ダメージ履歴</h2>
            {damageHistory.length > 0 ? (
              <div className="space-y-1.5 max-h-96 overflow-y-auto">
                {damageHistory.map((event: DamageEvent, i: number) => (
                  <div key={i} className="flex items-center gap-2 p-2 rounded bg-gray-800/50 text-xs">
                    <span className="text-gray-500">T{event.turn}</span>
                    <span className="text-gray-300 flex-1">{event.name}</span>
                    <span className="font-mono text-red-400">-{event.damage_percent.toFixed(1)}%</span>
                    <span className="text-gray-500">
                      ({event.hp_before.toFixed(0)}% → {event.hp_after.toFixed(0)}%)
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-600 text-center py-8">
                ダメージ履歴なし
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
