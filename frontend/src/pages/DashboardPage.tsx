import { useContext, useState } from 'react'
import { BattleContext } from '../contexts/BattleContext'
import { SpeedTierPanel } from '../components/battle/SpeedTierPanel'
import { HPTrackerPanel } from '../components/battle/HPTrackerPanel'
import { FieldStatePanel } from '../components/battle/FieldStatePanel'
import { ProtectPanel } from '../components/battle/ProtectPanel'
import { TurnHistoryPanel } from '../components/battle/TurnHistoryPanel'
import { Play, Square, SkipForward } from 'lucide-react'

export function DashboardPage() {
  const battle = useContext(BattleContext)
  const [showStartForm, setShowStartForm] = useState(false)
  const [allyTeam, setAllyTeam] = useState('')
  const [enemyTeam, setEnemyTeam] = useState('')

  if (!battle) return null

  const { matchState, startMatch, advanceTurn, endMatch } = battle
  const phase = matchState?.phase || 'none'
  const isActive = phase === 'in_battle'

  const handleStart = async () => {
    const allies = allyTeam.split(',').map(s => s.trim()).filter(Boolean)
    const enemies = enemyTeam.split(',').map(s => s.trim()).filter(Boolean)
    await startMatch(allies, enemies)
    setShowStartForm(false)
  }

  return (
    <div className="space-y-4">
      {/* コントロールバー */}
      <div className="flex items-center gap-2">
        {phase === 'none' && (
          <>
            {showStartForm ? (
              <div className="flex-1 flex gap-2 items-end">
                <div className="flex-1">
                  <label className="text-[10px] text-gray-500">味方チーム (カンマ区切り)</label>
                  <input
                    className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-gray-200"
                    placeholder="ガブリアス,ニンフィア,リキキリン..."
                    value={allyTeam}
                    onChange={(e) => setAllyTeam(e.target.value)}
                  />
                </div>
                <div className="flex-1">
                  <label className="text-[10px] text-gray-500">相手チーム (カンマ区切り)</label>
                  <input
                    className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-gray-200"
                    placeholder="バンギラス,カイリュー..."
                    value={enemyTeam}
                    onChange={(e) => setEnemyTeam(e.target.value)}
                  />
                </div>
                <button
                  onClick={handleStart}
                  className="px-3 py-1.5 rounded bg-green-600 hover:bg-green-500 text-white text-xs font-medium"
                >
                  開始
                </button>
                <button
                  onClick={() => setShowStartForm(false)}
                  className="px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs"
                >
                  キャンセル
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowStartForm(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-green-600 hover:bg-green-500 text-white text-xs font-medium"
              >
                <Play className="w-3.5 h-3.5" />
                新しい試合
              </button>
            )}
          </>
        )}
        {isActive && (
          <>
            <button
              onClick={() => advanceTurn()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
            >
              <SkipForward className="w-3.5 h-3.5" />
              次のターン
            </button>
            <button
              onClick={() => endMatch('win')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-green-700 hover:bg-green-600 text-white text-xs font-medium"
            >
              勝利
            </button>
            <button
              onClick={() => endMatch('lose')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-red-700 hover:bg-red-600 text-white text-xs font-medium"
            >
              敗北
            </button>
            <button
              onClick={() => endMatch()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs"
            >
              <Square className="w-3.5 h-3.5" />
              終了
            </button>
          </>
        )}
        {phase === 'finished' && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">
              結果: <span className="text-white font-medium">{matchState?.result || '不明'}</span>
            </span>
            <button
              onClick={() => setShowStartForm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-green-600 hover:bg-green-500 text-white text-xs font-medium"
            >
              <Play className="w-3.5 h-3.5" />
              新しい試合
            </button>
          </div>
        )}
      </div>

      {/* メインパネル */}
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-4 space-y-4">
          <SpeedTierPanel />
          <FieldStatePanel />
        </div>
        <div className="col-span-4 space-y-4">
          <HPTrackerPanel />
          <ProtectPanel />
        </div>
        <div className="col-span-4">
          <TurnHistoryPanel />
        </div>
      </div>
    </div>
  )
}
