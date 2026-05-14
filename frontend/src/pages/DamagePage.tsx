import { Calculator } from 'lucide-react'
import { DamageCalcPanel } from '../components/battle/DamageCalcPanel'

export function DamagePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold text-gray-200 flex items-center gap-2">
        <Calculator className="w-5 h-5 text-orange-400" />
        ダメージ計算
      </h1>
      <div className="max-w-2xl">
        <DamageCalcPanel />
      </div>
    </div>
  )
}
