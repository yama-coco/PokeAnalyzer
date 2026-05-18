import { useContext } from 'react'
import { BattleContext } from '../../contexts/BattleContext'
import { Heart } from 'lucide-react'
import type { PokemonOnField } from '../../types/battle'

function HPBar({ pokemon }: { pokemon: PokemonOnField }) {
  const isAlly = pokemon.side === 'ally'
  const percent = pokemon.hp_percent

  let barColor = 'bg-green-500'
  if (percent <= 25) barColor = 'bg-red-500'
  else if (percent <= 50) barColor = 'bg-yellow-500'

  return (
    <div className={`p-3 rounded-lg border ${
      isAlly ? 'bg-blue-950/30 border-blue-800/30' : 'bg-red-950/30 border-red-800/30'
    }`}>
      <div className="flex items-center justify-between mb-1.5">
        <span className={`text-sm font-medium ${isAlly ? 'text-blue-300' : 'text-red-300'}`}>
          {pokemon.name}
        </span>
        <span className="text-xs text-gray-400">
          {isAlly ? `Slot ${pokemon.slot}` : `Slot ${pokemon.slot}`}
        </span>
      </div>
      <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
        />
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-xs text-gray-400">
          {pokemon.status && (
            <span className="text-yellow-400 mr-1">{pokemon.status}</span>
          )}
        </span>
        <span className="text-xs font-mono text-gray-300">
          {isAlly && pokemon.max_hp > 0
            ? `${pokemon.current_hp}/${pokemon.max_hp}`
            : `${percent.toFixed(0)}%`
          }
        </span>
      </div>
    </div>
  )
}

export function HPTrackerPanel() {
  const battle = useContext(BattleContext)
  if (!battle) return null

  const { matchState } = battle
  const pokemon = matchState?.pokemon_on_field || []
  const allies = pokemon.filter((p: PokemonOnField) => p.side === 'ally')
  const enemies = pokemon.filter((p: PokemonOnField) => p.side === 'enemy')

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2 mb-3">
        <Heart className="w-4 h-4 text-red-400" />
        HP追跡
      </h2>

      {pokemon.length > 0 ? (
        <div className="space-y-4">
          {allies.length > 0 && (
            <div>
              <p className="text-[10px] text-blue-500 uppercase tracking-wider mb-1.5">味方</p>
              <div className="space-y-1.5">
                {allies.map((p: PokemonOnField) => <HPBar key={p.slot} pokemon={p} />)}
              </div>
            </div>
          )}
          {enemies.length > 0 && (
            <div>
              <p className="text-[10px] text-red-500 uppercase tracking-wider mb-1.5">相手</p>
              <div className="space-y-1.5">
                {enemies.map((p: PokemonOnField) => <HPBar key={p.slot} pokemon={p} />)}
              </div>
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs text-gray-600 text-center py-4">
          バトル開始後に表示されます
        </p>
      )}
    </div>
  )
}
