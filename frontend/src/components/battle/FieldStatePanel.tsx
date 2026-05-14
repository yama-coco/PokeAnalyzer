import { useContext, useState } from 'react'
import { BattleContext } from '../../contexts/BattleContext'
import { Cloud, Wind, RotateCcw, Leaf, Sun, Droplets, Mountain, Snowflake } from 'lucide-react'

const weatherIcons: Record<string, { icon: typeof Sun; label: string; color: string }> = {
  sun: { icon: Sun, label: '晴れ', color: 'text-orange-400' },
  rain: { icon: Droplets, label: '雨', color: 'text-blue-400' },
  sand: { icon: Mountain, label: '砂嵐', color: 'text-yellow-600' },
  snow: { icon: Snowflake, label: '雪', color: 'text-cyan-300' },
}

const terrainLabels: Record<string, string> = {
  grassy: 'グラスフィールド',
  electric: 'エレキフィールド',
  psychic: 'サイコフィールド',
  misty: 'ミストフィールド',
}

export function FieldStatePanel() {
  const battle = useContext(BattleContext)
  const [updating, setUpdating] = useState(false)

  if (!battle) return null
  const { matchState, updateField } = battle
  const field = matchState?.field_state

  const handleToggle = async (key: string, value: unknown) => {
    setUpdating(true)
    try {
      await updateField({ [key]: value })
    } finally {
      setUpdating(false)
    }
  }

  if (!field) return null

  const weatherInfo = weatherIcons[field.weather]

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2 mb-3">
        <Cloud className="w-4 h-4 text-gray-400" />
        フィールド状態
      </h2>

      <div className="grid grid-cols-2 gap-2">
        {/* 天候 */}
        <div className="col-span-2 flex items-center justify-between p-2 rounded bg-gray-800/50">
          <div className="flex items-center gap-2 text-xs">
            {weatherInfo ? (
              <>
                <weatherInfo.icon className={`w-4 h-4 ${weatherInfo.color}`} />
                <span>{weatherInfo.label}</span>
                {field.weather_turns_left > 0 && (
                  <span className="text-gray-500">({field.weather_turns_left}T)</span>
                )}
              </>
            ) : (
              <span className="text-gray-500">天候なし</span>
            )}
          </div>
          <select
            className="text-xs bg-gray-700 text-gray-300 rounded px-1.5 py-0.5 border border-gray-600"
            value={field.weather}
            onChange={(e) => handleToggle('weather', e.target.value)}
            disabled={updating}
          >
            <option value="none">なし</option>
            <option value="sun">晴れ</option>
            <option value="rain">雨</option>
            <option value="sand">砂嵐</option>
            <option value="snow">雪</option>
          </select>
        </div>

        {/* 味方追い風 */}
        <button
          onClick={() => handleToggle('tailwind_ally', !field.tailwind_ally)}
          disabled={updating}
          className={`flex items-center gap-1.5 p-2 rounded text-xs transition ${
            field.tailwind_ally
              ? 'bg-blue-900/50 text-blue-300 border border-blue-700'
              : 'bg-gray-800/50 text-gray-500 border border-gray-700 hover:border-gray-600'
          }`}
        >
          <Wind className="w-3.5 h-3.5" />
          味方追い風
          {field.tailwind_ally && field.tailwind_ally_turns > 0 && (
            <span className="text-[10px]">({field.tailwind_ally_turns}T)</span>
          )}
        </button>

        {/* 相手追い風 */}
        <button
          onClick={() => handleToggle('tailwind_enemy', !field.tailwind_enemy)}
          disabled={updating}
          className={`flex items-center gap-1.5 p-2 rounded text-xs transition ${
            field.tailwind_enemy
              ? 'bg-red-900/50 text-red-300 border border-red-700'
              : 'bg-gray-800/50 text-gray-500 border border-gray-700 hover:border-gray-600'
          }`}
        >
          <Wind className="w-3.5 h-3.5" />
          相手追い風
          {field.tailwind_enemy && field.tailwind_enemy_turns > 0 && (
            <span className="text-[10px]">({field.tailwind_enemy_turns}T)</span>
          )}
        </button>

        {/* トリックルーム */}
        <button
          onClick={() => handleToggle('trick_room', !field.trick_room)}
          disabled={updating}
          className={`flex items-center gap-1.5 p-2 rounded text-xs transition ${
            field.trick_room
              ? 'bg-purple-900/50 text-purple-300 border border-purple-700'
              : 'bg-gray-800/50 text-gray-500 border border-gray-700 hover:border-gray-600'
          }`}
        >
          <RotateCcw className="w-3.5 h-3.5" />
          トリックルーム
          {field.trick_room && field.trick_room_turns > 0 && (
            <span className="text-[10px]">({field.trick_room_turns}T)</span>
          )}
        </button>

        {/* テレイン */}
        <div className="flex items-center gap-1.5 p-2 rounded bg-gray-800/50 text-xs">
          <Leaf className="w-3.5 h-3.5 text-green-500" />
          <span className={field.terrain ? 'text-green-300' : 'text-gray-500'}>
            {field.terrain ? terrainLabels[field.terrain] || field.terrain : 'テレインなし'}
          </span>
        </div>
      </div>
    </div>
  )
}
