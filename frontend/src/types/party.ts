export interface Pokemon {
  name: string
  ability: string
  item: string
  tera_type: string
  moves: string[]
  nature: string
  evs: { hp: number; attack: number; defense: number; sp_attack: number; sp_defense: number; speed: number }
  ivs: { hp: number; attack: number; defense: number; sp_attack: number; sp_defense: number; speed: number }
  actual_stats: { hp: number; attack: number; defense: number; sp_attack: number; sp_defense: number; speed: number }
  mega_stone: string
}

export interface Party {
  id: number
  name: string
  pokemon: Pokemon[]
  created_at: string
  updated_at: string
}
