import type { Party } from '../types/party'
import { api } from './client'

export const partyApi = {
  getAll: () => api.get<Party[]>('/party/'),

  getById: (id: number) => api.get<Party>(`/party/${id}`),

  create: (data: { name: string; pokemon_json: string }) =>
    api.post<Party>('/party/', data),

  update: (id: number, data: { name?: string; pokemon_json?: string }) =>
    api.put<Party>(`/party/${id}`, data),

  delete: (id: number) => api.delete<void>(`/party/${id}`),
}
