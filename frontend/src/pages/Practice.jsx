import { useState, useEffect, useRef } from 'react'
import { Send, Square, RefreshCw } from 'lucide-react'
import { sessionService } from '../services/api'
import { useUser } from '../context/UserContext'
import './Practice.css'

const MODES = [
  {
    key: 'conversation',
    icon: '💬',
    title: 'Conversation Practice',
    desc: 'Open-ended dialogue to build fluency and confidence.',
    hint: 'Focus this session entirely on natural conversation practice. Keep corrections brief and encourage the learner to keep talking.',
  },
  {
    key: 'daily',
    icon: '📅',
    title: 'Daily Exercise',
    desc: 'Quick review of your weakest areas for today.',
    hint: 'Run a fast daily review: 3–5 exercises covering the learner\'s most recent errors and spaced-repetition vocabulary due today.',
  },
  {
    key: 'grammar',
    icon: '📐',
    title: 'Grammar Drill',
    desc: 'Targeted practice of grammar rules and patterns.',
    hint: 'Focus exclusively on grammar drills. Give targeted exercises, explain rules clearly, and correct every grammatical mistake.',
  },
  {
    key: 'vocabulary',
    icon: '📖',
    title: 'Vocabulary Drill',
    desc: 'Build and review vocabulary with spaced repetition.',
    hint: 'Run a vocabulary drill session. Introduce new words, test recall, use them in sentences, and review any due flashcards.',
  },
]

export default function Practice() {
  const { profile } = useUser()
  const [selectedMode, setSelectedMode] = useState(null)
  const [drillActive, setDrillActive] = useState(false)
  const [messages, setMessages] = useState([])
  const [inputText, setInputText] = useState('')
  const [thinking, setThinking] = useState(false)
  const [loading, setLoading] = useState(false)
  const [sessionEnded, setSessionEnded] = useState(false)
  const msgsEndRef = useRef(null)

  useEffect(() => {
    msgsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  const addMsg = (role, content) =>
    setMessages(prev => [...prev, { id: Date.now() + Math.random(), role, content }])

  const startDrill = async (mode) => {
    setSelectedMode(mode)
    setMessages([])
    setSessionEnded(false)
    setInputText('')
    setLoading(true)
    setDrillActive(false)

    try {
      await sessionService.end(profile.profile_id).catch(() => {})
      const res = await sessionService.start(profile.profile_id, 'text')
      setDrillActive(true)

      const primeRes = await sessionService.message(
        profile.profile_id,
        `[PRACTICE MODE: ${mode.title}] ${mode.hint} Please start the ${mode.title.toLowerCase()} session now.`
      )
      addMsg('assistant', primeRes.reply)

      if (primeRes.session_complete) {
        setDrillActive(false)
        setSessionEnded(true)
      }
    } catch {
      addMsg('system', 'Could not start drill. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  const sendMessage = async () => {
    const text = inputText.trim()
    if (!text || thinking) return
    setInputText('')
    addMsg('user', text)
    setThinking(true)
    try {
      const res = await sessionService.message(profile.profile_id, text)
      addMsg('assistant', res.reply)
      if (res.session_complete) {
        setDrillActive(false)
        setSessionEnded(true)
        addMsg('system', 'Drill complete! Great work.')
      }
    } catch {
      addMsg('system', 'Failed to send — please try again.')
    } finally {
      setThinking(false)
    }
  }

  const endDrill = async () => {
    if (!drillActive) return
    setThinking(true)
    try {
      await sessionService.end(profile.profile_id)
    } catch { /* ignore */ }
    setDrillActive(false)
    setSessionEnded(true)
    addMsg('system', 'Drill ended.')
    setThinking(false)
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  const resetDrill = () => {
    setSelectedMode(null)
    setDrillActive(false)
    setMessages([])
    setSessionEnded(false)
  }

  return (
    <div className="practice fade-up">
      <div className="practice-header">
        <h2>Practice</h2>
        <p>Choose a focused drill to sharpen a specific skill.</p>
      </div>

      {/* Mode picker */}
      <div className="practice-grid">
        {MODES.map(mode => (
          <button
            key={mode.key}
            className={`practice-card ${selectedMode?.key === mode.key ? 'selected' : ''}`}
            onClick={() => startDrill(mode)}
            disabled={loading || thinking}
          >
            <span className="practice-card-icon">{mode.icon}</span>
            <span className="practice-card-title">{mode.title}</span>
            <span className="practice-card-desc">{mode.desc}</span>
          </button>
        ))}
      </div>

      {/* Drill panel */}
      {selectedMode ? (
        <div className="drill-area fade-up">
          <div className="drill-header">
            <div className="drill-title">
              <span>{selectedMode.icon}</span>
              <span>{selectedMode.title}</span>
              {drillActive && <span className="live-dot" style={{ width: 7, height: 7, background: 'var(--green)', borderRadius: '50%', animation: 'pulse 1.8s ease infinite' }} />}
            </div>
            <div className="drill-controls">
              {sessionEnded && (
                <button className="btn btn-ghost btn-sm" onClick={resetDrill}>
                  <RefreshCw size={13} /> New drill
                </button>
              )}
              {drillActive && (
                <button className="btn btn-danger btn-sm" onClick={endDrill}>
                  <Square size={11} /> End
                </button>
              )}
            </div>
          </div>

          <div className="drill-messages">
            {loading && (
              <div className="drill-msg drill-msg-system">
                <div className="drill-bubble">
                  <span className="spinner" style={{ width: 14, height: 14, marginRight: 6 }} />
                  Starting {selectedMode.title.toLowerCase()}…
                </div>
              </div>
            )}

            {messages.map(msg => (
              <DrillBubble key={msg.id} msg={msg} />
            ))}

            {thinking && (
              <div className="drill-thinking">
                <span style={{ animationDelay: '0s' }} />
                <span style={{ animationDelay: '0.2s' }} />
                <span style={{ animationDelay: '0.4s' }} />
              </div>
            )}

            <div ref={msgsEndRef} />
          </div>

          {drillActive && !sessionEnded && (
            <div className="drill-input-row">
              <textarea
                className="drill-textarea"
                placeholder="Your answer…"
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                onKeyDown={handleKey}
                rows={1}
                disabled={thinking}
              />
              <button
                className="btn btn-primary drill-send-btn"
                onClick={sendMessage}
                disabled={!inputText.trim() || thinking}
              >
                {thinking ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <Send size={15} />}
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="drill-area">
          <div className="practice-empty">
            <div className="practice-empty-icon">🎯</div>
            <p>Select a drill above to begin a focused practice session.</p>
          </div>
        </div>
      )}
    </div>
  )
}

function DrillBubble({ msg }) {
  const cls = `drill-msg drill-msg-${msg.role}`
  return (
    <div className={cls}>
      {msg.role === 'assistant' && (
        <div className="drill-avatar">T</div>
      )}
      <div className="drill-bubble">{msg.content}</div>
    </div>
  )
}
