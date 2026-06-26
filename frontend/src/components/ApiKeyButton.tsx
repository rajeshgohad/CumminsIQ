import { KeyRound, X, Eye, EyeOff, CheckCircle2 } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'

interface Props {
  apiKey: string
  onChange: (key: string) => void
}

export default function ApiKeyButton({ apiKey, onChange }: Props) {
  const [open, setOpen]       = useState(false)
  const [draft, setDraft]     = useState('')
  const [show, setShow]       = useState(false)
  const [saved, setSaved]     = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const isSet = apiKey.length > 0

  useEffect(() => {
    if (open) { setDraft(apiKey); setTimeout(() => inputRef.current?.focus(), 50) }
  }, [open])

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  function save() {
    onChange(draft.trim())
    setSaved(true)
    setTimeout(() => { setSaved(false); setOpen(false) }, 900)
  }

  function clear() { onChange(''); setDraft(''); setOpen(false) }

  return (
    <div className="relative" ref={panelRef}>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(o => !o)}
        title={isSet ? 'Anthropic API key set (session only)' : 'Set Anthropic API key'}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium transition-all ${
          isSet
            ? 'bg-violet-500/10 border-violet-500/30 text-violet-400 hover:bg-violet-500/20'
            : 'bg-white/5 border-white/10 text-gray-500 hover:text-gray-300 hover:border-white/20'
        }`}
      >
        <KeyRound size={11} />
        <span>{isSet ? 'API Key ✓' : 'API Key'}</span>
      </button>

      {/* Popover */}
      {open && (
        <div className="absolute right-0 top-10 w-80 bg-[#0D1220] border border-white/12 rounded-xl shadow-2xl z-[100] overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/8">
            <div className="flex items-center gap-2">
              <KeyRound size={13} className="text-violet-400" />
              <span className="text-[12px] font-semibold text-white">Anthropic API Key</span>
            </div>
            <button onClick={() => setOpen(false)} className="text-gray-600 hover:text-white">
              <X size={14} />
            </button>
          </div>

          <div className="px-4 py-3 flex flex-col gap-3">
            <p className="text-[10px] text-gray-500 leading-relaxed">
              Stored in memory only — cleared when you close or refresh the tab. Never sent anywhere except directly to the Anthropic API.
            </p>

            <div className="relative">
              <input
                ref={inputRef}
                type={show ? 'text' : 'password'}
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') save() }}
                placeholder="sk-ant-api03-..."
                className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-[11px] font-mono text-white placeholder-gray-600 pr-8 focus:outline-none focus:border-violet-500/50"
              />
              <button
                onClick={() => setShow(s => !s)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400"
              >
                {show ? <EyeOff size={12} /> : <Eye size={12} />}
              </button>
            </div>

            <div className="flex gap-2">
              <button
                onClick={save}
                className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-[11px] font-semibold bg-violet-600 hover:bg-violet-500 text-white transition-colors"
              >
                {saved ? <><CheckCircle2 size={12} /> Saved</> : 'Save for session'}
              </button>
              {isSet && (
                <button
                  onClick={clear}
                  className="px-3 py-2 rounded-lg text-[11px] text-gray-400 hover:text-white border border-white/10 hover:border-white/20 transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
