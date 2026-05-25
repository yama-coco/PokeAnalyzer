export interface PokemonTemplate {
  species: string
  archetype_name: string
  ability: string
  item: string
  nature: string
  evs: Record<string, number>
  moves: string[]
  usage_rate: number
  tera_type: string | null
  can_mega_evolve: boolean
  notes: string
  source_url: string
}

export interface KeyPokemonInfo {
  species: string
  role: string
  priority: string
}

export interface TeamAnalysisResponse {
  archetype: string
  key_pokemon: KeyPokemonInfo[]
  threats: string[]
  pokemon_details: Record<string, PokemonTemplate[]>
}

export interface UsageRankingEntry {
  rank: number
  species: string
  usage_rate: number
  top_archetype: string
  template_count: number
}

export interface UsageRankingResponse {
  ranking: UsageRankingEntry[]
  total_pokemon: number
  total_templates: number
  last_updated: string
}
