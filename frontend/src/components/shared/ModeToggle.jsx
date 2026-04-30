import { Keyboard, Mic } from 'lucide-react'

export default function ModeToggle({ mode, onChange, disabled = false }) {
  return (
    <div className="mode-toggle" role="group" aria-label="Input mode">
      <button
        className={`mode-btn${mode === 'text' ? ' active' : ''}`}
        onClick={() => onChange('text')}
        disabled={disabled}
        aria-pressed={mode === 'text'}
        title="Switch to text input"
      >
        <Keyboard size={12} />
        Text
      </button>
      <button
        className={`mode-btn${mode === 'voice' ? ' active' : ''}`}
        onClick={() => onChange('voice')}
        disabled={disabled}
        aria-pressed={mode === 'voice'}
        title="Switch to voice input"
      >
        <Mic size={12} />
        Voice
      </button>
    </div>
  )
}
