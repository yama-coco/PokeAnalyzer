import { useState } from 'react'
import { Gauge } from 'lucide-react'
import { battleApi } from '../api/battle'
import type { SpeedEntry } from '../types/battle'
import { SpeedTierPanel } from '../components/battle/SpeedTierPanel'
import { FieldStatePanel } from '../components/battle/FieldStatePanel'

interface PokemonInput {
  name: string
  base_speed: number
  slot: number
  item: string
  ability: string
  is_paralyzed: boolean
  speed_modifier: number
}

const defaultPokemon: PokemonInput = {
  name: '',
  base_speed: 0,
  slot: 0,
  item: '',
  ability: '',
  is_paralyzed: false,
  speed_modifier: 0,
}

export function SpeedPage() {
  const [pokemon, setPokemon] = useState<PokemonInput[]>([
    { ...defaultPokemon, slot: 0 },
    { ...defaultPokemon, slot: 1 },
    { ...defaultPokemon, slot: 2 },
    { ...defaultPokemon, slot: 3 },
  ])
  const [field, setField] = useState({
    trick_room: false,
    tailwind_ally: false,
    tailwind_enemy: false,
    weather: 'none',
  })
  const [result, setResult] = useState<SpeedEntry[]>([])
  const [loading, setLoading] = useState(false)

  const handleCalc = async () => {
    setLoading(true)
    try {
      const filtered = pokemon.filter(p => p.name && p.base_speed > 0)
      const res = await battleApi.calcSpeedTiers(filtered as unknown as Record<string, unknown>[], field)
      setResult(res.tiers)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const updatePokemon = (index: number, updates: Partial<PokemonInput>) => {
    setPokemon(prev => prev.map((p, i) => i === index ? { ...p, ...updates } : p))
  }

  const inputClass = 'w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-blue-500'

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold text-gray-200 flex items-center gap-2">
        <Gauge className="w-5 h-5 text-yellow-400" />
        素早さ計算機
      </h1>

      <div className="grid grid-cols-12 gap-4">
        {/* 入力フォーム */}
        <div className="col-span-8">
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
            <div className="grid grid-cols-2 gap-3">
              {pokemon.map((p, i) => (
                <div key={i} className={`p-3 rounded-lg border ${
                  i < 2 ? 'bg-blue-950/20 border-blue-800/30' : 'bg-red-950/20 border-red-800/30'
                }`}>
                  <p className="text-[10px] text-gray-500 mb-1.5">
                    {i < 2 ? '味方' : '相手'} Slot {i}
                  </p>
                  <div className="space-y-1.5">
                    <input
                      placeholder="ポケモン名"
                      className={inputClass}
                      value={p.name}
                      onChange={(e) => updatePokemon(i, { name: e.target.value })}
                    />
                    <div className="grid grid-cols-2 gap-1.5">
                      <input
                        placeholder="S実数値"
                        type="number"
                        className={inputClass}
                        value={p.base_speed || ''}
                        onChange={(e) => updatePokemon(i, { base_speed: parseInt(e.target.value) || 0 })}
                      />
                      <select
                        className={inputClass}
                        value={p.speed_modifier}
                        onChange={(e) => updatePokemon(i, { speed_modifier: parseInt(e.target.value) })}
                      >
                        {[-6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6].map(v => (
                          <option key={v} value={v}>ランク {v >= 0 ? `+${v}` : v}</option>
                        ))}
                      </select>
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      <input
                        placeholder="持ち物"
                        className={inputClass}
                        value={p.item}
                        onChange={(e) => updatePokemon(i, { item: e.target.value })}
                      />
                      <input
                        placeholder="特性"
                        className={inputClass}
                        value={p.ability}
                        onChange={(e) => updatePokemon(i, { ability: e.target.value })}
                      />
                    </div>
                    <label className="flex items-center gap-1.5 text-xs text-gray-400">
                      <input
                        type="checkbox"
                        checked={p.is_paralyzed}
                        onChange={(e) => updatePokemon(i, { is_paralyzed: e.target.checked })}
                      />
                      まひ
                    </label>
                  </div>
                </div>
              ))}
            </div>

            {/* フィールド条件 */}
            <div className="mt-3 flex gap-3 items-center">
              <label className="flex items-center gap-1.5 text-xs text-gray-400">
                <input
                  type="checkbox"
                  checked={field.trick_room}
                  onChange={(e) => setField(f => ({ ...f, trick_room: e.target.checked }))}
                />
                トリックルーム
              </label>
              <label className="flex items-center gap-1.5 text-xs text-gray-400">
                <input
                  type="checkbox"
                  checked={field.tailwind_ally}
                  onChange={(e) => setField(f => ({ ...f, tailwind_ally: e.target.checked }))}
                />
                味方追い風
              </label>
              <label className="flex items-center gap-1.5 text-xs text-gray-400">
                <input
                  type="checkbox"
                  checked={field.tailwind_enemy}
                  onChange={(e) => setField(f => ({ ...f, tailwind_enemy: e.target.checked }))}
                />
                相手追い風
              </label>
              <select
                className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-300"
                value={field.weather}
                onChange={(e) => setField(f => ({ ...f, weather: e.target.value }))}
              >
                <option value="none">天候なし</option>
                <option value="sun">晴れ</option>
                <option value="rain">雨</option>
                <option value="sand">砂嵐</option>
                <option value="snow">雪</option>
              </select>
            </div>

            <button
              onClick={handleCalc}
              disabled={loading}
              className="w-full mt-3 py-2 rounded bg-yellow-600 hover:bg-yellow-500 text-white text-sm font-medium disabled:opacity-50 transition"
            >
              {loading ? '計算中...' : '素早さ順を計算'}
            </button>

            {result.length > 0 && (
              <div className="mt-3 space-y-1.5">
                {result.map((entry, i) => (
                  <div key={i} className={`flex items-center gap-3 p-2 rounded ${
                    entry.side === 'ally' ? 'bg-blue-950/30' : 'bg-red-950/30'
                  }`}>
                    <span className="w-6 h-6 flex items-center justify-center rounded-full bg-gray-700 text-xs font-bold">
                      {entry.order}
                    </span>
                    <span className={`flex-1 text-sm ${
                      entry.side === 'ally' ? 'text-blue-300' : 'text-red-300'
                    }`}>
                      {entry.name}
                    </span>
                    <span className="font-mono text-sm text-white">{entry.effective_speed}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* サイドパネル */}
        <div className="col-span-4 space-y-4">
          <SpeedTierPanel />
          <FieldStatePanel />
        </div>
      </div>
    </div>
  )
}
