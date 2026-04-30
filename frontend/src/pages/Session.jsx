import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Send, Square, BookOpen, ChevronDown, ChevronUp } from 'lucide-react'

import { sessionService, voiceService } from '../services/api'
import voiceSvc from '../services/voiceService'
import { useUser } from '../context/UserContext'

import ModeToggle from '../components/shared/ModeToggle'
import VoiceRecorder from '../components/voice/VoiceRecorder'
import AudioPlayer from '../components/voice/AudioPlayer'
import TranscriptDisplay from '../components/voice/TranscriptDisplay'

import './Session.css'

const MAX_EXCHANGES = parseInt(import.meta.env.VITE_MAX_EXCHANGES || '8', 10)

export default function Session() {
  const { profile } = useUser()
  const navigate = useNavigate()
  const messagesEndRef   = useRef(null)
  const sessionStartedRef = useRef(false)   // guard against StrictMode double-invoke

  const [messages, setMessages]           = useState([])
  const [inputText, setInputText]         = useState('')
  const [mode, setMode]                   = useState('text')
  const [sessionActive, setSessionActive] = useState(false)
  const [loading, setLoading]             = useState(false)
  const [agentThinking, setAgentThinking] = useState(false)
  const [planSummary, setPlanSummary]     = useState(null)
  const [showPlan, setShowPlan]           = useState(false)
  const [sessionEnded, setSessionEnded]   = useState(false)
  const [summary, setSummary]             = useState(null)
  const [exchangeCount, setExchangeCount] = useState(0)

  // Latest voice result for TranscriptDisplay
  const [voiceResult, setVoiceResult] = useState(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentThinking])

  useEffect(() => {
    if (!profile) { navigate('/'); return }
    // Guard: StrictMode mounts twice in dev — only start the session once
    if (sessionStartedRef.current) return
    sessionStartedRef.current = true
    startSession()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const startSession = async () => {
    setLoading(true)
    setExchangeCount(0)
    try {
      await sessionService.end(profile.profile_id).catch(() => {})
      const res = await sessionService.start(profile.profile_id, mode)
      setSessionActive(true)
      setPlanSummary(res.plan_summary)
      addMessage('assistant', res.opening_message)
    } catch {
      addMessage('system', 'Could not start session. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  const addMessage = (role, content, meta = {}) => {
    setMessages(prev => [
      ...prev,
      { id: Date.now() + Math.random(), role, content, timestamp: new Date(), ...meta },
    ])
  }

  const handleSessionComplete = async () => {
    setSessionActive(false)
    setAgentThinking(true)
    try {
      const res = await sessionService.end(profile.profile_id)
      setSessionEnded(true)
      setSummary(res)
    } catch {
      addMessage('system', 'Session limit reached. Could not retrieve summary.')
      setSessionEnded(true)
    } finally {
      setAgentThinking(false)
    }
  }

  // ── Text send ──────────────────────────────────────────────────────────────
  const handleTextSend = async () => {
    const text = inputText.trim()
    if (!text || agentThinking) return
    setInputText('')
    addMessage('user', text)
    setAgentThinking(true)
    setExchangeCount(n => n + 1)
    try {
      const res = await sessionService.message(profile.profile_id, text)
      addMessage('assistant', res.reply)
      if (res.session_complete) await handleSessionComplete()
    } catch {
      addMessage('system', 'Failed to send — please try again.')
    } finally {
      setAgentThinking(false)
    }
  }

  // ── Voice send ─────────────────────────────────────────────────────────────
  const handleVoiceSend = async (audioBlob) => {
    setAgentThinking(true)
    setVoiceResult(null)
    setExchangeCount(n => n + 1)

    // Build a local URL so the user can replay what they sent
    const recordingUrl = URL.createObjectURL(audioBlob)

    try {
      const res = await voiceSvc.sessionMessage(
        audioBlob,
        profile.profile_id,
        profile.target_language,
        profile.overall_level || '',   // learnerLevel — controls TTS speed
        '',                             // expectedText — empty for free conversation
      )

      setVoiceResult(res)

      // User bubble — include the recording URL for in-bubble playback
      addMessage('user', res.user_transcript, {
        recordingUrl,
        confidence: res.transcription_confidence,
        pronunciation: res.pronunciation,
      })

      // Assistant bubble — audioB64 arrives pre-baked from the voice pipeline
      addMessage('assistant', res.agent_reply, {
        audioB64: res.agent_audio_b64,
        audioContentType: res.agent_audio_content_type,
      })

      if (res.session_complete) await handleSessionComplete()
    } catch (err) {
      URL.revokeObjectURL(recordingUrl)
      const detail = err?.response?.data?.detail
      addMessage('system', detail || 'Voice processing failed — try again or switch to text.')
    } finally {
      setAgentThinking(false)
    }
  }

  const handleEndSession = async () => {
    if (!sessionActive) return
    setSessionActive(false)
    setAgentThinking(true)
    try {
      const res = await sessionService.end(profile.profile_id)
      setSessionEnded(true)
      setSummary(res)
    } catch {
      addMessage('system', 'Could not end session cleanly.')
    } finally {
      setAgentThinking(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleTextSend() }
  }

  if (!profile) return null

  // ── Session ended — summary screen ────────────────────────────────────────
  if (sessionEnded && summary) {
    const score    = Math.round(summary.performance_score || 0)
    const congrats = score >= 80 ? '🎉 Excellent work!'
      : score >= 60 ? '👏 Good session!'
      : score >= 40 ? '💪 Keep going!'
      : '📚 Every session counts!'

    return (
      <div className="session-summary fade-up">
        <div className="summary-card card">
          <div className="summary-congrats">{congrats}</div>

          <div className="summary-score">
            <span className="score-number">{score}</span>
            <span className="score-label">/ 100</span>
          </div>

          <h2 style={{ marginBottom: '0.5rem' }}>Session complete</h2>

          {summary.summary && (
            <p className="summary-text mt-1">{summary.summary}</p>
          )}

          <div className="summary-stats mt-3">
            <div className="stat">
              <span className="stat-value">{summary.exercises_correct || 0}/{summary.exercises_completed || 0}</span>
              <span className="stat-label">Correct</span>
            </div>
            <div className="stat">
              <span className="stat-value">{summary.errors_made || 0}</span>
              <span className="stat-label">Errors</span>
            </div>
            <div className="stat">
              <span className="stat-value">{summary.mastered_concepts?.length || 0}</span>
              <span className="stat-label">Mastered</span>
            </div>
          </div>

          {summary.mastered_concepts?.length > 0 && (
            <div className="summary-mastered mt-3">
              <p className="small muted" style={{ marginBottom: '0.4rem' }}>What you mastered today</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', justifyContent: 'center' }}>
                {summary.mastered_concepts.map((c, i) => (
                  <span key={i} className="tag tag-green" style={{ fontSize: '0.75rem' }}>{c}</span>
                ))}
              </div>
            </div>
          )}

          <div className="summary-actions mt-3">
            <button
              className="btn btn-primary"
              onClick={() => {
                setSessionEnded(false)
                setMessages([])
                setSummary(null)
                setExchangeCount(0)
                sessionStartedRef.current = false
                startSession()
              }}
            >
              Start new session
            </button>
            <button className="btn btn-ghost" onClick={() => navigate('/progress')}>
              View progress
            </button>
          </div>
        </div>
      </div>
    )
  }

  const exchangePct = Math.min((exchangeCount / MAX_EXCHANGES) * 100, 100)

  return (
    <div className="session">
      {/* ── Header ── */}
      <div className="session-header">
        <div className="session-header-left">
          <BookOpen size={16} className="amber" />
          <span className="session-lang">{profile.target_language} session</span>
          {sessionActive && <span className="live-dot" />}
        </div>
        <div className="session-header-right">
          {sessionActive && (
            <div className="exchange-counter" title={`${exchangeCount} / ${MAX_EXCHANGES} exchanges`}>
              <div className="exchange-bar">
                <div
                  className="exchange-bar-fill"
                  style={{
                    width: `${exchangePct}%`,
                    background: exchangePct >= 75 ? 'var(--red)' : 'var(--amber)',
                  }}
                />
              </div>
              <span className="exchange-label">{exchangeCount}/{MAX_EXCHANGES}</span>
            </div>
          )}

          <button
            className="plan-toggle btn btn-ghost btn-sm"
            onClick={() => setShowPlan(p => !p)}
          >
            Today's plan {showPlan ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>

          <ModeToggle mode={mode} onChange={setMode} disabled={agentThinking} />

          {sessionActive && (
            <button className="btn btn-danger btn-sm" onClick={handleEndSession}>
              <Square size={12} /> End
            </button>
          )}
        </div>
      </div>

      {/* ── Plan panel ── */}
      {showPlan && planSummary && (
        <div className="plan-panel fade-in">
          <div className="plan-focus">
            {Object.entries(planSummary.focus || {}).map(([k, v]) => (
              <div key={k} className="focus-item">
                <span className="focus-label">{k}</span>
                <div className="progress-bar">
                  <div className="progress-bar-fill" style={{ width: `${v}%` }} />
                </div>
                <span className="focus-pct">{v}%</span>
              </div>
            ))}
          </div>
          {planSummary.reasoning && (
            <p className="plan-reasoning small muted mt-1">
              <em>Agent's reasoning:</em> {planSummary.reasoning}
            </p>
          )}
          {planSummary.review_count > 0 && (
            <span className="tag tag-amber mt-1">
              {planSummary.review_count} vocab reviews due
            </span>
          )}
        </div>
      )}

      {/* ── Messages ── */}
      <div className="messages">
        {loading && (
          <div className="msg-loading fade-in">
            <span className="spinner" /> Starting your session…
          </div>
        )}

        {messages.map(msg => (
          <MessageBubble
            key={msg.id}
            msg={msg}
            targetLanguage={profile.target_language}
            learnerLevel={profile.overall_level || ''}
          />
        ))}

        {agentThinking && (
          <div className="thinking-bubble fade-in">
            <span className="dot-1" /><span className="dot-2" /><span className="dot-3" />
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Input area ── */}
      {sessionActive && (
        <div className="session-input">
          {mode === 'text' ? (
            <div className="text-input-row">
              <textarea
                className="chat-input"
                placeholder="Type in the target language…"
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                disabled={agentThinking}
              />
              <button
                className="btn btn-primary send-btn"
                onClick={handleTextSend}
                disabled={!inputText.trim() || agentThinking}
              >
                {agentThinking ? <span className="spinner" /> : <Send size={16} />}
              </button>
            </div>
          ) : (
            <div className="voice-mode-area">
              {voiceResult && (
                <TranscriptDisplay
                  transcript={voiceResult.user_transcript}
                  confidence={voiceResult.transcription_confidence}
                  pronunciation={voiceResult.pronunciation}
                />
              )}
              <VoiceRecorder
                onRecordingComplete={handleVoiceSend}
                disabled={!sessionActive}
                processing={agentThinking}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Message content parser ─────────────────────────────────────────────────────

function parseContent(content) {
  const parts = []
  const regex = /\[CORRECTION\]([\s\S]*?)\[\/CORRECTION\]/g
  let lastIndex = 0
  let match

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: content.slice(lastIndex, match.index) })
    }
    parts.push({ type: 'correction', content: match[1].trim() })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < content.length) {
    parts.push({ type: 'text', content: content.slice(lastIndex) })
  }
  return parts.filter(p => p.content.trim())
}

// ── MessageBubble ──────────────────────────────────────────────────────────────

function MessageBubble({ msg, targetLanguage, learnerLevel = '' }) {
  const isUser   = msg.role === 'user'
  const isSystem = msg.role === 'system'

  // For text-mode assistant messages: fetch TTS on demand
  const [ttsUrl, setTtsUrl]       = useState(null)
  const [ttsLoading, setTtsLoading] = useState(false)

  if (isSystem) {
    return <div className="msg-system small muted">{msg.content}</div>
  }

  const parts = parseContent(msg.content || '')

  // Fetch TTS audio on demand (only for text-mode messages without pre-baked audio)
  const handleFetchTts = async () => {
    if (ttsUrl || ttsLoading) return
    setTtsLoading(true)
    try {
      const url = await voiceService.speak(msg.content, targetLanguage, learnerLevel)
      setTtsUrl(url)
    } catch { /* fail silently */ }
    finally { setTtsLoading(false) }
  }

  return (
    <div className={`msg-row ${isUser ? 'msg-user' : 'msg-assistant'} fade-up`}>
      {!isUser && <div className="msg-avatar">T</div>}
      <div className="msg-bubble">

        {/* Text + correction blocks */}
        {parts.map((part, i) =>
          part.type === 'correction' ? (
            <CorrectionCard key={i} content={part.content} />
          ) : (
            <span key={i} style={{ whiteSpace: 'pre-wrap' }}>{part.content}</span>
          )
        )}

        {/* Pronunciation warning (voice mode) */}
        {msg.pronunciation?.has_errors && (
          <div className="pronunciation-hint small">
            ⚠ {msg.pronunciation.feedback}
          </div>
        )}

        {/* Low audio quality */}
        {msg.confidence !== undefined && msg.confidence < 0.25 && (
          <div className="confidence-hint small muted">
            Hard to hear — try speaking louder or closer to the mic
          </div>
        )}

        {/* ── User bubble: replay their recording ── */}
        {isUser && msg.recordingUrl && (
          <div className="msg-actions">
            <AudioPlayer
              audioUrl={msg.recordingUrl}
              autoPlay={false}
              label="Your recording"
            />
          </div>
        )}

        {/* ── Assistant bubble: pre-baked audio (voice mode) or on-demand TTS ── */}
        {!isUser && (
          <div className="msg-actions">
            {msg.audioB64 ? (
              /* Voice-mode reply: audio arrives pre-baked → auto-play + seek bar */
              <AudioPlayer
                audioB64={msg.audioB64}
                contentType={msg.audioContentType || 'audio/mpeg'}
                autoPlay={true}
                label="Replay"
              />
            ) : ttsUrl ? (
              /* TTS was fetched on demand — show the full AudioPlayer */
              <AudioPlayer
                audioUrl={ttsUrl}
                autoPlay={true}
                label="Replay"
              />
            ) : (
              /* Not yet fetched — show a "Listen" trigger button */
              <button
                className="btn-listen small muted"
                onClick={handleFetchTts}
                disabled={ttsLoading}
                title="Hear pronunciation"
              >
                {ttsLoading
                  ? <span className="spinner" style={{ width: 12, height: 12 }} />
                  : '🔊'
                }
                {ttsLoading ? ' Loading…' : ' Listen'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── CorrectionCard ─────────────────────────────────────────────────────────────

function CorrectionCard({ content }) {
  const lines = content.split('\n').filter(Boolean)

  return (
    <div className="correction-card">
      {lines.map((line, i) => {
        const isSaid    = line.startsWith('❌')
        const isCorrect = line.startsWith('✅')
        const isRule    = line.startsWith('📖')
        return (
          <div
            key={i}
            className={`correction-line ${isSaid ? 'correction-said' : isCorrect ? 'correction-fix' : isRule ? 'correction-rule' : ''}`}
          >
            {line}
          </div>
        )
      })}
    </div>
  )
}
