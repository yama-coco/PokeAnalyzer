export interface PokemonOnField {
  slot: number
  name: string
  species: string
  ability: string
  item: string
  base_speed: number
  speed_modifier: number
  is_paralyzed: boolean
  current_hp: number
  max_hp: number
  hp_percent: number
  side: 'ally' | 'enemy'
  is_mega_evolved: boolean
  is_terastallized: boolean
  tera_type: string
  status: string
}

export interface FieldState {
  weather: string
  weather_turns_left: number
  tailwind_ally: boolean
  tailwind_ally_turns: number
  tailwind_enemy: boolean
  tailwind_enemy_turns: number
  trick_room: boolean
  trick_room_turns: number
  terrain: string
  terrain_turns: number
}

export interface TurnRecord {
  turn: number
  timestamp: number
  actions: Record<string, unknown>[]
  field_before: FieldState | null
  field_after: FieldState | null
  speed_order: SpeedEntry[]
  hp_changes: Record<string, unknown>[]
}

export interface MatchState {
  match_id: string
  phase: 'none' | 'team_preview' | 'selection' | 'in_battle' | 'finished'
  turn: number
  ally_team: string[]
  enemy_team: string[]
  ally_leads: string[]
  enemy_leads: string[]
  pokemon_on_field: PokemonOnField[]
  field_state: FieldState
  turn_history: TurnRecord[]
  result: string
}

export interface SpeedEntry {
  order: number
  slot: number
  name: string
  base_speed: number
  effective_speed: number
  side: 'ally' | 'enemy'
}

export interface SpeedOrderResponse {
  turn: number
  trick_room: boolean
  speed_order: SpeedEntry[]
}

export interface DamageResult {
  min_damage: number
  max_damage: number
  min_percent: number
  max_percent: number
}

export interface ProtectState {
  name: string
  consecutive_uses: number
  total_uses: number
  total_successes: number
  next_success_rate: number
  last_used_turn: number
  history: { turn: number; move: string; success: boolean }[]
}

export interface HPState {
  [slot: number]: {
    name: string
    current_hp: number
    max_hp: number
    hp_percent: number
    source: string
  }
}

export interface DamageEvent {
  turn: number
  slot: number
  name: string
  damage_percent: number
  hp_before: number
  hp_after: number
}

export interface TurnLog {
  turn: number
  actions: TurnAction[]
  speed_order: SpeedEntry[]
  hp_snapshot: Record<string, unknown>
  field_snapshot: Record<string, unknown>
}

export interface TurnAction {
  turn: number
  pokemon_slot: number
  pokemon_name: string
  action_type: string
  action_name: string
  target_slot: number | null
  target_name: string
}
