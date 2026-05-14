import { createContext } from 'react'
import type { useBattleState } from '../hooks/useBattleState'

type BattleContextType = ReturnType<typeof useBattleState> & {
  wsConnected: boolean
}

export const BattleContext = createContext<BattleContextType | null>(null)
