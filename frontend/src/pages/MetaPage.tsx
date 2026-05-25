import { useState, useEffect } from 'react'
import { Search, TrendingUp, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react'
import { metaApi } from '../api/meta'
import type {
  PokemonTemplate,
  TeamAnalysisResponse,
  UsageRankingEntry,
} from '../types/meta'

const EV_LABELS: Record<string, string> = {
  hp: 'H',
  attack: 'A',
  defense: 'B',
  sp_attack: 'C',
  sp_defense: 'D',
  speed: 'S',
}

function formatEvs(evs: Record<string, number>): string {
  return Object.entries(evs)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => `${EV_LABELS[k] ?? k}${v}`)
    .join(' / ')
}

function TemplateCard({ template }: { template: PokemonTemplate }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="bg-gray-800/60 rounded-lg border border-gray-700/50 p-3">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-200">
            {template.archetype_name}
          </span>
          <span className="text-[10px] text-gray-500">
            使用率 {(template.usage_rate * 100).toFixed(1)}%
          </span>
          {template.can_mega_evolve && (
            <span className="text-[10px] bg-purple-900/50 text-purple-300 px-1.5 py-0.5 rounded">
              メガシンカ
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="w-3.5 h-3.5 text-gray-500" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
        )}
      </div>

      <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-gray-400">
        <div>
          <span className="text-gray-600">特性: </span>
          {template.ability || '-'}
        </div>
        <div>
          <span className="text-gray-600">持ち物: </span>
          {template.item || '-'}
        </div>
        <div>
          <span className="text-gray-600">性格: </span>
          {template.nature || '-'}
        </div>
      </div>

      <div className="mt-1.5 flex flex-wrap gap-1">
        {template.moves.map((move, i) => (
          <span
            key={i}
            className="text-[11px] bg-gray-700/50 text-gray-300 px-1.5 py-0.5 rounded"
          >
            {move}
          </span>
        ))}
      </div>

      {expanded && (
        <div className="mt-2 space-y-1 text-xs text-gray-500">
          {Object.keys(template.evs).length > 0 && (
            <div>
              <span className="text-gray-600">努力値: </span>
              {formatEvs(template.evs)}
            </div>
          )}
          {template.tera_type && (
            <div>
              <span className="text-gray-600">テラスタイプ: </span>
              {template.tera_type}
            </div>
          )}
          {template.notes && (
            <div>
              <span className="text-gray-600">備考: </span>
              {template.notes}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function MetaPage() {
  const [enemyInput, setEnemyInput] = useState<string[]>(['', '', '', '', '', ''])
  const [analysis, setAnalysis] = useState<TeamAnalysisResponse | null>(null)
  const [singleSearch, setSingleSearch] = useState('')
  const [singleResult, setSingleResult] = useState<PokemonTemplate[]>([])
  const [ranking, setRanking] = useState<UsageRankingEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'team' | 'search' | 'ranking'>('team')

  useEffect(() => {
    metaApi.getUsageRanking(20).then((res) => setRanking(res.ranking)).catch(() => {})
  }, [])

  const handleTeamAnalysis = async () => {
    const species = enemyInput.filter((s) => s.trim())
    if (species.length === 0) {
      setError('1体以上入力してください')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await metaApi.analyzeTeam(species)
      setAnalysis(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : '分析に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const handleSingleSearch = async () => {
    if (!singleSearch.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await metaApi.getPokemonTemplates(singleSearch.trim())
      setSingleResult(res)
      if (res.length === 0) {
        setError(`${singleSearch} のデータが見つかりません`)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '検索に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  const updateEnemy = (index: number, value: string) => {
    setEnemyInput((prev) => prev.map((v, i) => (i === index ? value : v)))
  }

  const inputClass =
    'w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-blue-500'

  const tabClass = (tab: string) =>
    `px-3 py-1.5 text-xs rounded-t-lg transition-colors ${
      activeTab === tab
        ? 'bg-gray-800 text-blue-400 border-b-2 border-blue-400'
        : 'text-gray-500 hover:text-gray-300'
    }`

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold text-gray-200 flex items-center gap-2">
        <Search className="w-5 h-5 text-green-400" />
        メタゲーム型検索
      </h1>

      {/* タブ */}
      <div className="flex gap-1 border-b border-gray-800">
        <button className={tabClass('team')} onClick={() => setActiveTab('team')}>
          チーム分析
        </button>
        <button className={tabClass('search')} onClick={() => setActiveTab('search')}>
          個別検索
        </button>
        <button className={tabClass('ranking')} onClick={() => setActiveTab('ranking')}>
          使用率ランキング
        </button>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-800/50 rounded-lg px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      {/* チーム分析タブ */}
      {activeTab === 'team' && (
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-4">
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
              <h2 className="text-sm font-medium text-gray-300 mb-3">相手の6体</h2>
              <div className="space-y-2">
                {enemyInput.map((val, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-[10px] text-gray-600 w-4">{i + 1}</span>
                    <input
                      className={inputClass}
                      placeholder={`ポケモン ${i + 1}`}
                      value={val}
                      onChange={(e) => updateEnemy(i, e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleTeamAnalysis()
                      }}
                    />
                  </div>
                ))}
              </div>
              <button
                className="mt-3 w-full bg-blue-600 hover:bg-blue-500 text-white text-xs py-2 rounded-lg transition-colors disabled:opacity-50"
                onClick={handleTeamAnalysis}
                disabled={loading}
              >
                {loading ? '分析中...' : '分析する'}
              </button>
            </div>
          </div>

          <div className="col-span-8">
            {analysis && (
              <div className="space-y-4">
                {/* 構築タイプ */}
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
                  <h2 className="text-sm font-medium text-gray-300 mb-2">構築タイプ推定</h2>
                  <p className="text-lg font-bold text-blue-400">{analysis.archetype}</p>
                </div>

                {/* 軸ポケモン */}
                {analysis.key_pokemon.length > 0 && (
                  <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
                    <h2 className="text-sm font-medium text-gray-300 mb-2 flex items-center gap-1.5">
                      <TrendingUp className="w-3.5 h-3.5 text-yellow-400" />
                      軸ポケモン
                    </h2>
                    <div className="space-y-1.5">
                      {analysis.key_pokemon.map((kp, i) => (
                        <div
                          key={i}
                          className="flex items-center gap-2 text-xs"
                        >
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] ${
                              kp.priority === '高'
                                ? 'bg-red-900/50 text-red-300'
                                : kp.priority === '中'
                                  ? 'bg-yellow-900/50 text-yellow-300'
                                  : 'bg-gray-700 text-gray-400'
                            }`}
                          >
                            {kp.priority}
                          </span>
                          <span className="text-gray-200 font-medium">{kp.species}</span>
                          <span className="text-gray-500">{kp.role}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 警戒ポイント */}
                {analysis.threats.length > 0 && (
                  <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
                    <h2 className="text-sm font-medium text-gray-300 mb-2 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-orange-400" />
                      警戒ポイント
                    </h2>
                    <div className="space-y-1">
                      {analysis.threats.map((threat, i) => (
                        <p key={i} className="text-xs text-orange-300/80">
                          {threat}
                        </p>
                      ))}
                    </div>
                  </div>
                )}

                {/* 各ポケモンの型詳細 */}
                {Object.entries(analysis.pokemon_details).map(([species, templates]) => (
                  <div
                    key={species}
                    className="bg-gray-900 rounded-xl border border-gray-800 p-4"
                  >
                    <h3 className="text-sm font-bold text-gray-200 mb-2">{species}</h3>
                    {templates.length === 0 ? (
                      <p className="text-xs text-gray-600">データなし</p>
                    ) : (
                      <div className="space-y-2">
                        {templates.map((t, i) => (
                          <TemplateCard key={i} template={t} />
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 個別検索タブ */}
      {activeTab === 'search' && (
        <div className="max-w-xl">
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
            <h2 className="text-sm font-medium text-gray-300 mb-3">ポケモン名で型を検索</h2>
            <div className="flex gap-2">
              <input
                className={inputClass}
                placeholder="ポケモン名 (例: ガブリアス)"
                value={singleSearch}
                onChange={(e) => setSingleSearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSingleSearch()
                }}
              />
              <button
                className="bg-blue-600 hover:bg-blue-500 text-white text-xs px-4 rounded-lg transition-colors whitespace-nowrap disabled:opacity-50"
                onClick={handleSingleSearch}
                disabled={loading}
              >
                検索
              </button>
            </div>
          </div>

          {singleResult.length > 0 && (
            <div className="mt-4 bg-gray-900 rounded-xl border border-gray-800 p-4">
              <h3 className="text-sm font-bold text-gray-200 mb-3">
                {singleSearch} の型一覧 ({singleResult.length} 件)
              </h3>
              <div className="space-y-2">
                {singleResult.map((t, i) => (
                  <TemplateCard key={i} template={t} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 使用率ランキングタブ */}
      {activeTab === 'ranking' && (
        <div className="max-w-xl">
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
            <h2 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-yellow-400" />
              使用率ランキング
            </h2>
            {ranking.length === 0 ? (
              <p className="text-xs text-gray-600">データがありません</p>
            ) : (
              <div className="space-y-1">
                {ranking.map((entry) => (
                  <div
                    key={entry.rank}
                    className="flex items-center gap-3 py-1.5 border-b border-gray-800/50 last:border-0"
                  >
                    <span className="text-xs text-gray-600 w-6 text-right">
                      {entry.rank}
                    </span>
                    <span className="text-sm text-gray-200 flex-1 font-medium">
                      {entry.species}
                    </span>
                    <span className="text-xs text-gray-500">
                      {entry.top_archetype}
                    </span>
                    <span className="text-xs text-blue-400 w-14 text-right">
                      {(entry.usage_rate * 100).toFixed(1)}%
                    </span>
                    <span className="text-[10px] text-gray-600">
                      {entry.template_count}型
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
