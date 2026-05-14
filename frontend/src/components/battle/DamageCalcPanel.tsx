import { useState } from 'react'
import { Calculator } from 'lucide-react'
import { battleApi } from '../../api/battle'
import type { DamageResult } from '../../types/battle'

export function DamageCalcPanel() {
  const [form, setForm] = useState({
    move_name: '',
    move_power: 0,
    move_category: 'physical' as 'physical' | 'special',
    is_spread: false,
    attacker_name: '',
    attacker_stat: 0,
    attacker_item: '',
    has_stab: false,
    type_effectiveness: 1.0,
    defender_name: '',
    defender_stat: 0,
    defender_max_hp: 0,
  })
  const [result, setResult] = useState<DamageResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleCalc = async () => {
    if (!form.move_power || !form.attacker_stat || !form.defender_stat || !form.defender_max_hp) {
      setError('必須項目を入力してください')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await battleApi.calcDamage(form)
      setResult(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : '計算エラー')
    } finally {
      setLoading(false)
    }
  }

  const inputClass = 'w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-blue-500'

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2 mb-3">
        <Calculator className="w-4 h-4 text-orange-400" />
        ダメージ計算
      </h2>

      <div className="grid grid-cols-2 gap-3">
        {/* 攻撃側 */}
        <div className="space-y-2">
          <p className="text-[10px] text-blue-400 uppercase tracking-wider">攻撃側</p>
          <input
            placeholder="ポケモン名"
            className={inputClass}
            value={form.attacker_name}
            onChange={(e) => setForm(f => ({ ...f, attacker_name: e.target.value }))}
          />
          <input
            placeholder="攻撃/特攻実数値"
            type="number"
            className={inputClass}
            value={form.attacker_stat || ''}
            onChange={(e) => setForm(f => ({ ...f, attacker_stat: parseInt(e.target.value) || 0 }))}
          />
          <input
            placeholder="持ち物"
            className={inputClass}
            value={form.attacker_item}
            onChange={(e) => setForm(f => ({ ...f, attacker_item: e.target.value }))}
          />
          <label className="flex items-center gap-1.5 text-xs text-gray-400">
            <input
              type="checkbox"
              checked={form.has_stab}
              onChange={(e) => setForm(f => ({ ...f, has_stab: e.target.checked }))}
              className="rounded"
            />
            タイプ一致
          </label>
        </div>

        {/* 防御側 */}
        <div className="space-y-2">
          <p className="text-[10px] text-red-400 uppercase tracking-wider">防御側</p>
          <input
            placeholder="ポケモン名"
            className={inputClass}
            value={form.defender_name}
            onChange={(e) => setForm(f => ({ ...f, defender_name: e.target.value }))}
          />
          <input
            placeholder="防御/特防実数値"
            type="number"
            className={inputClass}
            value={form.defender_stat || ''}
            onChange={(e) => setForm(f => ({ ...f, defender_stat: parseInt(e.target.value) || 0 }))}
          />
          <input
            placeholder="最大HP"
            type="number"
            className={inputClass}
            value={form.defender_max_hp || ''}
            onChange={(e) => setForm(f => ({ ...f, defender_max_hp: parseInt(e.target.value) || 0 }))}
          />
        </div>

        {/* 技情報 */}
        <div className="col-span-2 space-y-2">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">技</p>
          <div className="grid grid-cols-3 gap-2">
            <input
              placeholder="技名"
              className={inputClass}
              value={form.move_name}
              onChange={(e) => setForm(f => ({ ...f, move_name: e.target.value }))}
            />
            <input
              placeholder="威力"
              type="number"
              className={inputClass}
              value={form.move_power || ''}
              onChange={(e) => setForm(f => ({ ...f, move_power: parseInt(e.target.value) || 0 }))}
            />
            <select
              className={inputClass}
              value={form.move_category}
              onChange={(e) => setForm(f => ({ ...f, move_category: e.target.value as 'physical' | 'special' }))}
            >
              <option value="physical">物理</option>
              <option value="special">特殊</option>
            </select>
          </div>
          <div className="flex gap-4">
            <label className="flex items-center gap-1.5 text-xs text-gray-400">
              <input
                type="checkbox"
                checked={form.is_spread}
                onChange={(e) => setForm(f => ({ ...f, is_spread: e.target.checked }))}
                className="rounded"
              />
              範囲技
            </label>
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              <span>タイプ相性:</span>
              <select
                className="bg-gray-800 border border-gray-700 rounded px-1 py-0.5 text-xs"
                value={form.type_effectiveness}
                onChange={(e) => setForm(f => ({ ...f, type_effectiveness: parseFloat(e.target.value) }))}
              >
                <option value={0.25}>0.25x</option>
                <option value={0.5}>0.5x</option>
                <option value={1.0}>1x</option>
                <option value={2.0}>2x</option>
                <option value={4.0}>4x</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <button
        onClick={handleCalc}
        disabled={loading}
        className="w-full mt-3 py-2 rounded bg-orange-600 hover:bg-orange-500 text-white text-sm font-medium disabled:opacity-50 transition"
      >
        {loading ? '計算中...' : 'ダメージ計算'}
      </button>

      {error && <p className="text-xs text-red-400 mt-2">{error}</p>}

      {result && (
        <div className="mt-3 p-3 rounded-lg bg-gray-800/50 border border-gray-700">
          <div className="text-center">
            <span className="text-2xl font-bold font-mono text-orange-400">
              {result.min_percent}% 〜 {result.max_percent}%
            </span>
          </div>
          <div className="text-center text-xs text-gray-500 mt-1">
            ({result.min_damage} 〜 {result.max_damage} ダメージ)
          </div>
        </div>
      )}
    </div>
  )
}
