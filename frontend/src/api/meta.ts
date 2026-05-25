import type {
  PokemonTemplate,
  TeamAnalysisResponse,
  UsageRankingResponse,
} from '../types/meta'
import { api } from './client'

export const metaApi = {
  getPokemonTemplates: (species: string) =>
    api.get<PokemonTemplate[]>(`/meta/pokemon/${encodeURIComponent(species)}`),

  analyzeTeam: (enemySpecies: string[]) =>
    api.post<TeamAnalysisResponse>('/meta/analyze-team', {
      enemy_species: enemySpecies,
    }),

  updateMeta: (species: string, templates: PokemonTemplate[]) =>
    api.post<{ status: string; species: string; template_count: number }>(
      '/meta/update',
      { species, templates },
    ),

  getUsageRanking: (limit = 50) =>
    api.get<UsageRankingResponse>(`/meta/usage-ranking?limit=${limit}`),
}
