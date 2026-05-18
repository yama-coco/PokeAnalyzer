import { Circle } from 'lucide-react'

interface HeaderProps {
  phase: string
  turn: number
  isConnected: boolean
}

const phaseLabels: Record<string, string> = {
  none: '待機中',
  team_preview: 'チームプレビュー',
  selection: '選出',
  in_battle: 'バトル中',
  finished: '終了',
}

const phaseColors: Record<string, string> = {
  none: 'bg-gray-600',
  team_preview: 'bg-yellow-500',
  selection: 'bg-orange-500',
  in_battle: 'bg-green-500',
  finished: 'bg-blue-500',
}

export function Header({ phase, turn, isConnected }: HeaderProps) {
  return (
    <header className="h-12 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-4">
      <div className="flex items-center gap-4">
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium text-white ${phaseColors[phase] || 'bg-gray-600'}`}>
          {phaseLabels[phase] || phase}
        </span>
        {phase === 'in_battle' && (
          <span className="text-sm text-gray-400">
            ターン <span className="text-white font-mono">{turn}</span>
          </span>
        )}
      </div>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <Circle
          className={`w-2.5 h-2.5 ${isConnected ? 'text-green-400 fill-green-400' : 'text-red-400 fill-red-400'}`}
        />
        {isConnected ? '接続中' : '未接続'}
      </div>
    </header>
  )
}
