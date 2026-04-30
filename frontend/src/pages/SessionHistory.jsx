import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp, Clock, CheckCircle, AlertCircle } from 'lucide-react'
import { sessionHistoryService } from '../services/api'
import { useUser } from '../context/UserContext'
import { LANG_FLAGS, LANG_LABELS } from '../utils/languages'
import './SessionHistory.css'

/** Parse a naive UTC ISO string from the backend and return a proper Date. */
function parseUTC(isoStr) {
  if (!isoStr) return new Date()
  // Backend stores UTC datetimes without timezone suffix — append 'Z' so JS treats it as UTC
  const s = isoStr.endsWith('Z') || isoStr.includes('+') ? isoStr : isoStr + 'Z'
  return new Date(s)
}

export default function SessionHistory() {
  const { profile } = useUser()
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState('')

  const langName = LANG_LABELS[profile?.target_language] || profile?.target_language || 'this language'
  const langFlag = LANG_FLAGS[profile?.target_language]  || '🌐'

  useEffect(() => {
    if (!profile) return
    // Re-fetch whenever the active language profile changes
    setLoading(true)
    setError('')
    setSessions([])
    sessionHistoryService.all(profile.profile_id)
      .then(data => setSessions(data.sessions || []))
      .catch(() => setError('Could not load session history. Please try again.'))
      .finally(() => setLoading(false))
  }, [profile?.profile_id])

  if (loading) {
    return (
      <div className="history fade-up">
        <div className="history-header">
          <h2>Session History</h2>
          <span className="history-lang-pill">{langFlag} {langName}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-muted)', padding: '2rem 0' }}>
          <span className="spinner" /> Loading sessions…
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="history fade-up">
        <div className="history-header">
          <h2>Session History</h2>
          <span className="history-lang-pill">{langFlag} {langName}</span>
        </div>
        <div className="history-empty">
          <div className="history-empty-icon">⚠️</div>
          <p>{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="history fade-up">
      <div className="history-header">
        <div>
          <h2>Session History</h2>
          <p>{sessions.length} session{sessions.length !== 1 ? 's' : ''} completed</p>
        </div>
        <span className="history-lang-pill">{langFlag} {langName}</span>
      </div>

      {sessions.length === 0 ? (
        <div className="history-empty">
          <div className="history-empty-icon">📚</div>
          <h3>No sessions yet</h3>
          <p>Start a session in <strong>{langName}</strong> to see your history here.</p>
        </div>
      ) : (
        <div className="sessions-list">
          {sessions.map((session, i) => (
            <SessionCard
              key={session.id}
              session={session}
              index={sessions.length - i}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── SessionCard ───────────────────────────────────────────────────────────────

function SessionCard({ session, index }) {
  const [expanded, setExpanded] = useState(false)
  const [messages, setMessages] = useState(null)
  const [loadingMsgs, setLoadingMsgs] = useState(false)

  const toggle = async () => {
    if (!expanded && messages === null) {
      setLoadingMsgs(true)
      try {
        const data = await sessionHistoryService.messages(session.id)
        setMessages(data.messages || [])
      } catch {
        setMessages([])
      } finally {
        setLoadingMsgs(false)
      }
    }
    setExpanded(p => !p)
  }

  const startedAt = parseUTC(session.started_at)
  const dateStr   = startedAt.toLocaleDateString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
  })
  const timeStr = startedAt.toLocaleTimeString(undefined, {
    hour: '2-digit', minute: '2-digit',
  })

  const duration = session.duration_minutes
    ? `${Math.round(session.duration_minutes)} min`
    : null

  const score = session.performance_score != null
    ? Math.round(session.performance_score)
    : null

  const scoreColor = score == null ? 'var(--text-muted)'
    : score >= 75 ? 'var(--green)'
    : score >= 50 ? 'var(--amber)'
    : 'var(--red)'

  return (
    <div className="session-card">
      <div className="session-card-header" onClick={toggle} role="button" tabIndex={0}
        onKeyDown={e => e.key === 'Enter' && toggle()}>
        <div className="session-card-left">
          <div className="session-number">#{index}</div>
          <div className="session-meta">
            <span className="session-date">{dateStr} · {timeStr}</span>
            <div className="session-stats">
              {duration && (
                <span className="session-stat">
                  <Clock size={11} />
                  <span className="session-stat-val">{duration}</span>
                </span>
              )}
              {session.exercises_completed > 0 && (
                <span className="session-stat">
                  <CheckCircle size={11} />
                  <span className="session-stat-val">
                    {session.exercises_correct}/{session.exercises_completed}
                  </span>{' '}correct
                </span>
              )}
              {session.errors_made > 0 && (
                <span className="session-stat">
                  <AlertCircle size={11} />
                  <span className="session-stat-val">{session.errors_made}</span>{' '}error{session.errors_made !== 1 ? 's' : ''}
                </span>
              )}
              {session.session_type && (
                <span className="tag tag-muted" style={{ fontSize: '0.68rem', padding: '0.1rem 0.4rem' }}>
                  {session.session_type}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="session-card-right">
          {score != null && (
            <div className="session-score-wrap">
              <span className="session-score" style={{ color: scoreColor }}>{score}</span>
              <span className="session-score-label">/ 100</span>
            </div>
          )}
          {!session.completed && (
            <span className="tag tag-amber" style={{ fontSize: '0.7rem' }}>incomplete</span>
          )}
          <span className="expand-icon">
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </span>
        </div>
      </div>

      {session.agent_summary && (
        <div className="session-summary-row">
          <p className="summary-text">"{session.agent_summary}"</p>
        </div>
      )}

      {expanded && (
        <div className="session-transcript fade-in">
          {loadingMsgs ? (
            <div className="transcript-loading">
              <span className="spinner" style={{ width: 14, height: 14 }} />
              Loading transcript…
            </div>
          ) : messages && messages.length > 0 ? (
            <div className="transcript-msgs">
              {messages.map((m, i) => (
                <TranscriptMessage key={i} msg={m} />
              ))}
            </div>
          ) : (
            <p className="small muted" style={{ textAlign: 'center', padding: '1rem' }}>
              No messages recorded for this session.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

// ── TranscriptMessage ─────────────────────────────────────────────────────────

function TranscriptMessage({ msg }) {
  const role = msg.role === 'user' ? 'user' : msg.role === 'assistant' ? 'assistant' : 'system'
  const time = msg.timestamp
    ? parseUTC(msg.timestamp).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
    : null

  const cleanContent = msg.content
    ? msg.content.replace(/\[CORRECTION\][\s\S]*?\[\/CORRECTION\]/g, '[correction]').trim()
    : ''

  return (
    <div className={`tmsg tmsg-${role}`}>
      <div className="tmsg-bubble">{cleanContent}</div>
      {time && <span className="tmsg-time">{time}</span>}
    </div>
  )
}
