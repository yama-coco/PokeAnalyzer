import { Monitor } from 'lucide-react'

export function HUDPage() {
  const hudUrl = `${window.location.origin}/hud`

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold text-gray-200 flex items-center gap-2">
        <Monitor className="w-5 h-5 text-purple-400" />
        OBS HUD オーバーレイ
      </h1>

      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">設定方法</h2>
        <ol className="text-xs text-gray-400 space-y-2 list-decimal list-inside">
          <li>OBS Studioで「ブラウザソース」を追加</li>
          <li>URLに以下を入力:
            <code className="ml-1 px-2 py-0.5 rounded bg-gray-800 text-blue-300 select-all">{hudUrl}</code>
          </li>
          <li>幅: <code className="px-1 bg-gray-800 text-gray-200">1920</code>, 高さ: <code className="px-1 bg-gray-800 text-gray-200">1080</code></li>
          <li>「カスタムCSS」で背景を透明に設定済み</li>
        </ol>
      </div>

      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">プレビュー</h2>
        <div className="relative bg-black rounded-lg overflow-hidden" style={{ aspectRatio: '16/9' }}>
          <iframe
            src="/hud"
            className="w-full h-full border-0"
            title="HUD Preview"
          />
        </div>
      </div>
    </div>
  )
}
