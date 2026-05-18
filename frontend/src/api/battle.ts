import type {
  DamageResult,
  HPState,
  DamageEvent,
  MatchState,
  ProtectState,
  SpeedOrderResponse,
  TurnLog,
} from '../types/battle'
import { api } from './client'

export const battleApi = {
  startMatch: (allyTeam: string[], enemyTeam: string[]) =>
    api.post<MatchState>('/battle/match/start', {
      ally_team: allyTeam,
      enemy_team: enemyTeam,
    }),

  setSelection: (allyLeads: string[], enemyLeads: string[] = []) =>
    api.post<MatchState>('/battle/match/selection', {
      ally_leads: allyLeads,
      enemy_leads: enemyLeads,
    }),

  startBattle: (pokemonOnField: Record<string, unknown>[]) =>
    api.post<MatchState>('/battle/match/battle-start', {
      pokemon_on_field: pokemonOnField,
    }),

  getState: () => api.get<MatchState>('/battle/match/state'),

  getSpeedOrder: () => api.get<SpeedOrderResponse>('/battle/match/speed-order'),

  updateField: (field: {
    weather?: string
    tailwind_ally?: boolean
    tailwind_enemy?: boolean
    trick_room?: boolean
    terrain?: string
  }) => api.put<{ field_state: Record<string, unknown>; speed_order: SpeedOrderResponse['speed_order'] }>('/battle/match/field', field),

  advanceTurn: (actions: Record<string, unknown>[] = []) =>
    api.post<{ turn_record: Record<string, unknown>; current_turn: number; speed_order: SpeedOrderResponse['speed_order'] }>(
      '/battle/match/advance-turn',
      { actions },
    ),

  endMatch: (result: string = '') =>
    api.post<MatchState>(`/battle/match/end?result=${encodeURIComponent(result)}`),

  // HP
  updateHP: (slot: number, data: { current_hp?: number; max_hp?: number; hp_percent?: number }) =>
    api.put<{ damage_event: DamageEvent | null; hp_state: HPState }>('/battle/hp/update', { slot, ...data }),

  getHPState: () => api.get<HPState>('/battle/hp/state'),

  getDamageHistory: () => api.get<DamageEvent[]>('/battle/hp/damage-history'),

  // Damage calc
  calcDamage: (params: {
    move_name: string
    move_power: number
    move_category: string
    is_spread?: boolean
    attacker_name: string
    attacker_stat: number
    attacker_item?: string
    has_stab?: boolean
    type_effectiveness?: number
    defender_name: string
    defender_stat: number
    defender_max_hp: number
  }) => api.post<DamageResult>('/battle/damage/calc', params),

  // Protect
  recordProtect: (pokemonName: string, moveName: string, turn: number, success = true) =>
    api.post<ProtectState>('/battle/protect/record', {
      pokemon_name: pokemonName,
      move_name: moveName,
      turn,
      success,
    }),

  getProtectState: () => api.get<Record<string, ProtectState>>('/battle/protect/state'),

  getProtectForPokemon: (name: string) =>
    api.get<ProtectState>(`/battle/protect/${encodeURIComponent(name)}`),

  // Turn log
  logAction: (params: {
    turn: number
    pokemon_slot: number
    pokemon_name: string
    action_type: string
    action_name: string
    target_slot?: number
    target_name?: string
  }) => api.post<Record<string, unknown>>('/battle/log/action', params),

  commitTurn: (turn: number) =>
    api.post<TurnLog>(`/battle/log/commit-turn?turn=${turn}`),

  getAllLogs: () => api.get<TurnLog[]>('/battle/log/all'),

  getTurnLog: (turn: number) => api.get<TurnLog>(`/battle/log/turn/${turn}`),

  // Speed tiers (Phase 1)
  calcSpeedTiers: (pokemon: Record<string, unknown>[], field: Record<string, unknown>) =>
    api.post<{ tiers: SpeedOrderResponse['speed_order'] }>('/battle/speed-tiers', { pokemon, field }),
}
