export interface PokemonStats {
  hp: number
  attack: number
  defense: number
  sp_attack: number
  sp_defense: number
  speed: number
}

export interface PokemonEntry {
  species: string
  ability: string
  item: string
  moves: string[]
  stats: PokemonStats
  tera_type: string | null
  can_mega_evolve: boolean
}

export interface Party {
  id: number
  name: string
  pokemon: PokemonEntry[]
  created_at: string
  updated_at: string
}
