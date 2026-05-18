import { useEffect, useState } from 'react'
import { Users, Plus, Trash2, Edit2, Save, X } from 'lucide-react'
import { partyApi } from '../api/party'
import type { Party, PokemonEntry } from '../types/party'

export function PartyPage() {
  const [parties, setParties] = useState<Party[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [formName, setFormName] = useState('')
  const [formJson, setFormJson] = useState('')

  const fetchParties = async () => {
    try {
      const data = await partyApi.getAll()
      setParties(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'パーティの取得に失敗')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchParties()
  }, [])

  const handleSave = async () => {
    try {
      let pokemon: PokemonEntry[]
      try {
        pokemon = JSON.parse(formJson)
      } catch {
        setError('JSONの形式が正しくありません')
        return
      }
      if (editId !== null) {
        await partyApi.update(editId, { name: formName, pokemon })
      } else {
        await partyApi.create({ name: formName, pokemon })
      }
      setShowForm(false)
      setEditId(null)
      setFormName('')
      setFormJson('')
      fetchParties()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存に失敗')
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('削除しますか？')) return
    try {
      await partyApi.delete(id)
      fetchParties()
    } catch (e) {
      setError(e instanceof Error ? e.message : '削除に失敗')
    }
  }

  const handleEdit = (party: Party) => {
    setEditId(party.id)
    setFormName(party.name)
    setFormJson(JSON.stringify(party.pokemon, null, 2))
    setShowForm(true)
  }

  const inputClass = 'w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500'

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-gray-200 flex items-center gap-2">
          <Users className="w-5 h-5 text-green-400" />
          パーティ管理
        </h1>
        {!showForm && (
          <button
            onClick={() => { setShowForm(true); setEditId(null); setFormName(''); setFormJson('[]') }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-green-600 hover:bg-green-500 text-white text-xs font-medium"
          >
            <Plus className="w-3.5 h-3.5" />
            新規作成
          </button>
        )}
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {showForm && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">
            {editId !== null ? 'パーティ編集' : '新しいパーティ'}
          </h2>
          <div className="space-y-3">
            <input
              placeholder="パーティ名"
              className={inputClass}
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
            />
            <textarea
              placeholder='ポケモンJSON配列 [{"species": "ガブリアス", "ability": "さめはだ", "item": "", "moves": [], "stats": {"hp": 183, "attack": 200, "defense": 115, "sp_attack": 100, "sp_defense": 105, "speed": 169}, "tera_type": null, "can_mega_evolve": false}]'
              className={`${inputClass} h-48 font-mono text-xs`}
              value={formJson}
              onChange={(e) => setFormJson(e.target.value)}
            />
            <div className="flex gap-2">
              <button
                onClick={handleSave}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
              >
                <Save className="w-3.5 h-3.5" />
                保存
              </button>
              <button
                onClick={() => { setShowForm(false); setEditId(null) }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs"
              >
                <X className="w-3.5 h-3.5" />
                キャンセル
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-500">読み込み中...</p>
      ) : parties.length > 0 ? (
        <div className="space-y-2">
          {parties.map((party) => (
            <div key={party.id} className="bg-gray-900 rounded-xl border border-gray-800 p-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-200">{party.name}</h3>
                <div className="flex gap-1.5">
                  <button
                    onClick={() => handleEdit(party)}
                    className="p-1.5 rounded hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleDelete(party.id)}
                    className="p-1.5 rounded hover:bg-red-900/50 text-gray-500 hover:text-red-400 transition"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <div className="flex gap-2 flex-wrap">
                {(party.pokemon || []).map((p, i) => (
                  <span key={i} className="px-2 py-0.5 rounded bg-gray-800 text-xs text-gray-300">
                    {p.species || `ポケモン${i + 1}`}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-500 text-center py-8">
          パーティが登録されていません
        </p>
      )}
    </div>
  )
}
