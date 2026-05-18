import { Shield } from 'lucide-react'
import { ProtectPanel } from '../components/battle/ProtectPanel'

export function ProtectPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold text-gray-200 flex items-center gap-2">
        <Shield className="w-5 h-5 text-cyan-400" />
        まもる管理
      </h1>
      <div className="max-w-xl">
        <ProtectPanel />
      </div>
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 max-w-xl">
        <h3 className="text-sm font-semibold text-gray-300 mb-2">まもる成功確率表</h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="text-left py-1.5">連続回数</th>
              <th className="text-right py-1.5">成功確率</th>
              <th className="text-right py-1.5">計算式</th>
            </tr>
          </thead>
          <tbody className="text-gray-400">
            {[
              { n: 1, rate: '100%', formula: '1/1' },
              { n: 2, rate: '33.3%', formula: '1/3' },
              { n: 3, rate: '11.1%', formula: '1/9' },
              { n: 4, rate: '3.7%', formula: '1/27' },
              { n: 5, rate: '1.2%', formula: '1/81' },
              { n: 6, rate: '0.4%', formula: '1/243' },
            ].map(row => (
              <tr key={row.n} className="border-b border-gray-800/50">
                <td className="py-1.5">{row.n}回目</td>
                <td className="text-right font-mono text-gray-200">{row.rate}</td>
                <td className="text-right font-mono text-gray-500">{row.formula}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
