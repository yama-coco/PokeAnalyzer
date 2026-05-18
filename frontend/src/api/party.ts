import type { Party, PokemonEntry } from '../types/party'
import { api } from './client'

export const partyApi = {
  getAll: () => api.get<Party[]>('/parties/'),

  getById: (id: number) => api.get<Party>(`/parties/${id}`),

  create: (data: { name: string; pokemon: PokemonEntry[] }) =>
    api.post<Party>('/parties/', data),

  update: (id: number, data: { name?: string; pokemon?: PokemonEntry[] }) =>
    api.put<Party>(`/parties/${id}`, data),

  delete: (id: number) => api.delete<void>(`/parties/${id}`),
}
