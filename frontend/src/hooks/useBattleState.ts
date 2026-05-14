import { useState, useCallback, useEffect, useRef } from 'react'
import type { MatchState, SpeedOrderResponse, HPState, DamageEvent } from '../types/battle'
import { battleApi } from '../api/battle'

export function useBattleState() {
  const [matchState, setMatchState] = useState<MatchState | null>(null)
  const [speedOrder, setSpeedOrder] = useState<SpeedOrderResponse | null>(null)
  const [hpState, setHPState] = useState<HPState>({})
  const [damageHistory, setDamageHistory] = useState<DamageEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval>>(undefined)

  const refreshState = useCallback(async () => {
    try {
      const [state, speed, hp, damage] = await Promise.all([
        battleApi.getState(),
        battleApi.getSpeedOrder(),
        battleApi.getHPState(),
        battleApi.getDamageHistory(),
      ])
      setMatchState(state)
      setSpeedOrder(speed)
      setHPState(hp)
      setDamageHistory(damage)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch state')
    }
  }, [])

  const startMatch = useCallback(async (allyTeam: string[], enemyTeam: string[]) => {
    setLoading(true)
    try {
      const state = await battleApi.startMatch(allyTeam, enemyTeam)
      setMatchState(state)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start match')
    } finally {
      setLoading(false)
    }
  }, [])

  const setSelection = useCallback(async (allyLeads: string[], enemyLeads: string[] = []) => {
    try {
      const state = await battleApi.setSelection(allyLeads, enemyLeads)
      setMatchState(state)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to set selection')
    }
  }, [])

  const updateField = useCallback(async (field: Parameters<typeof battleApi.updateField>[0]) => {
    try {
      const result = await battleApi.updateField(field)
      setSpeedOrder(prev => prev ? { ...prev, speed_order: result.speed_order } : null)
      await refreshState()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update field')
    }
  }, [refreshState])

  const advanceTurn = useCallback(async (actions: Record<string, unknown>[] = []) => {
    try {
      await battleApi.advanceTurn(actions)
      await refreshState()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to advance turn')
    }
  }, [refreshState])

  const endMatch = useCallback(async (result: string = '') => {
    try {
      const state = await battleApi.endMatch(result)
      setMatchState(state)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to end match')
    }
  }, [])

  const startPolling = useCallback((intervalMs = 2000) => {
    pollingRef.current = setInterval(refreshState, intervalMs)
  }, [refreshState])

  const stopPolling = useCallback(() => {
    clearInterval(pollingRef.current)
  }, [])

  useEffect(() => {
    return () => clearInterval(pollingRef.current)
  }, [])

  return {
    matchState,
    speedOrder,
    hpState,
    damageHistory,
    loading,
    error,
    refreshState,
    startMatch,
    setSelection,
    updateField,
    advanceTurn,
    endMatch,
    startPolling,
    stopPolling,
  }
}
