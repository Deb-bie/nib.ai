import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CheckCircle, Plus, X, LogOut,
  BookOpen, MessageSquare, Mic, Headphones,
  PenLine, Trophy, Flame, Clock, TrendingUp,
} from 'lucide-react'
import { profileService } from '../services/api'
import { useUser } from '../context/UserContext'
import { LANG_FLAGS, LANG_LABELS } from '../utils/languages'
import './Profile.css'

// ── Helpers ───────────────────────────────────────────────────────────────────

const SKILL_META = {
  vocabulary: { icon: <BookOpen      size={14} />, label: 'Vocabulary' },
  grammar:    { icon: <PenLine       size={14} />, label: 'Grammar'    },
  speaking:   { icon: <Mic           size={14} />, label: 'Speaking'   },
  listening:  { icon: <Headphones    size={14} />, label: 'Listening'  },
  reading:    { icon: <BookOpen      size={14} />, label: 'Reading'    },
  writing:    { icon: <MessageSquare size={14} />, label: 'Writing'    },
}

const CEFR_ORDER = { unassessed: -1, A1: 0, A2: 1, B1: 2, B2: 3, C1: 4, C2: 5 }
const CEFR_COLOR = {
  unassessed: 'var(--text-muted)',
  A1: '#4a8fb5', A2: '#5a9e6f',
  B1: 'var(--amber)', B2: 'var(--amber)',
  C1: '#c8522a', C2: '#8b3cba',
}

function cefrProgress(level, score) {
  if (!level || level === 'unassessed') return 0
  const idx = CEFR_ORDER[level] ?? 0
  return Math.round((idx / 6) * 100 + (score || 0) / 6)
}

function formatMinutes(mins) {
  if (!mins) return '0 min'
  if (mins < 60) return `${mins} min`
  const h = Math.floor(mins / 60), m = mins % 60
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

function parseUTC(s) {
  if (!s) return new Date()
  return new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z')
}

// Mini sparkline SVG for recent session scores
function Sparkline({ sessions }) {
  const vals = (sessions || []).filter(s => s.performance_score != null).slice(0, 8).reverse()
  if (vals.length < 2) return null
  const W = 160, H = 44, pad = 5
  const xs = vals.map((_, i) => pad + (i / (vals.length - 1)) * (W - pad * 2))
  const ys = vals.map(s => H - pad - (s.performance_score / 100) * (H - pad * 2))
  const path = xs.map((x, i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' ')
  return (
    <svg width={W} height={H} style={{ overflow: 'visible', display: 'block' }}>
      <path d={path} fill="none" stroke="var(--amber)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      {vals.map((s, i) => (
        <circle key={i} cx={xs[i]} cy={ys[i]} r="3"
          fill="var(--amber)" opacity={i === vals.length - 1 ? 1 : 0.5} />
      ))}
    </svg>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function Profile() {
  const navigate = useNavigate()
  const { user, profile, allProfiles, switchProfile, addProfile, logout } = useUser()

  const [languages, setLanguages]       = useState([])
  const [showAddLang, setShowAddLang]   = useState(false)
  const [selectedLang, setSelectedLang] = useState('')
  const [adding, setAdding]             = useState(false)
  const [addError, setAddError]         = useState('')
  const [dashData, setDashData]         = useState(null)
  const [dashLoading, setDashLoading]   = useState(true)

  useEffect(() => {
    profileService.languages().then(d => setLanguages(d.languages || [])).catch(() => {})
  }, [])

  useEffect(() => {
    if (!profile) return
    setDashLoading(true)
    setDashData(null)
    profileService.dashboard(profile.profile_id)
      .then(setDashData)
      .catch(() => {})
      .finally(() => setDashLoading(false))
  }, [profile?.profile_id])

  const handleSwitch = (p) => {
    if (p.profile_id === profile?.profile_id) return
    switchProfile(p)
    navigate('/dashboard')
  }

  const handleAddLanguage = async () => {
    if (!selectedLang) return
    setAdding(true); setAddError('')
    try {
      const res = await profileService.addLanguage({ user_id: user.user_id, target_language: selectedLang })
      const np = { profile_id: res.profile_id, target_language: res.target_language, overall_level: res.overall_level }
      addProfile(np)
      setShowAddLang(false); setSelectedLang('')
      navigate('/assessment')
    } catch (e) {
      setAddError(e.response?.data?.detail || 'Could not add language. Please try again.')
    } finally {
      setAdding(false)
    }
  }

  if (!user) return null

  const learner  = dashData?.learner        || {}
  const vocab    = dashData?.vocabulary     || {}
  const errors   = dashData?.errors         || {}
  const recent   = dashData?.recent_sessions || []
  const skills   = learner.skills           || {}
  const initials = (user.username || 'U')[0].toUpperCase()
  const safeProfiles  = allProfiles || []
  const existingLangs = new Set(safeProfiles.map(p => p.target_language))

  const overallLevel = profile?.overall_level || 'unassessed'
  const levelColor   = CEFR_COLOR[overallLevel] || 'var(--text-muted)'
  const langName     = LANG_LABELS[profile?.target_language] || profile?.target_language || '—'
  const langFlag     = LANG_FLAGS[profile?.target_language]  || '🌐'

  const scoredSessions = recent.filter(s => s.performance_score != null)
  const avgScore = scoredSessions.length > 0
    ? Math.round(scoredSessions.reduce((s, r) => s + r.performance_score, 0) / scoredSessions.length)
    : null

  return (
    <div className="profile-page fade-up">

      {/* ── User identity ── */}
      <div className="card profile-user-card">
        <div className="profile-avatar">{initials}</div>
        <div className="profile-user-info">
          <span className="profile-username">{user.username}</span>
          {user.email && <span className="profile-email">{user.email}</span>}
        </div>
      </div>

      {/* ── Active language banner ── */}
      {profile && (
        <div className="card profile-lang-banner">
          <div className="plb-left">
            <span className="plb-flag">{langFlag}</span>
            <div>
              <div className="plb-lang">{langName}</div>
              <div className="plb-goal small muted">
                {learner.learning_goal
                  ? learner.learning_goal.charAt(0).toUpperCase() + learner.learning_goal.slice(1)
                  : 'General'} goal
              </div>
            </div>
          </div>
          <div className="plb-right">
            <span className="plb-level" style={{ color: levelColor }}>
              {overallLevel === 'unassessed' ? 'New learner' : overallLevel}
            </span>
            <span className="plb-level-label small muted">level</span>
          </div>
        </div>
      )}

      {/* ── Core stats ── */}
      <div className="card">
        <h3 style={{ marginBottom: '0.85rem' }}>Overview</h3>
        {dashLoading ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', color: 'var(--text-muted)', fontSize: '0.88rem' }}>
            <span className="spinner" style={{ width: 14, height: 14 }} /> Loading stats…
          </div>
        ) : (
          <div className="profile-stats">
            <div className="pstat">
              <Trophy size={18} style={{ color: 'var(--amber)', marginBottom: '0.2rem' }} />
              <span className="pstat-val">{learner.sessions_completed || 0}</span>
              <span className="pstat-lbl">Sessions</span>
            </div>
            <div className="pstat">
              <Flame size={18} style={{ color: 'var(--red)', marginBottom: '0.2rem' }} />
              <span className="pstat-val">{learner.streak_days || 0}</span>
              <span className="pstat-lbl">Day streak</span>
            </div>
            <div className="pstat">
              <Clock size={18} style={{ color: '#4a8fb5', marginBottom: '0.2rem' }} />
              <span className="pstat-val">{formatMinutes(learner.total_minutes_studied)}</span>
              <span className="pstat-lbl">Study time</span>
            </div>
            {avgScore != null && (
              <div className="pstat">
                <TrendingUp size={18} style={{ color: 'var(--green)', marginBottom: '0.2rem' }} />
                <span className="pstat-val">{avgScore}</span>
                <span className="pstat-lbl">Avg score</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Skills breakdown ── */}
      {!dashLoading && Object.keys(skills).length > 0 && (
        <div className="card">
          <div className="analytics-header">
            <h3>Skills</h3>
            <span className="small muted">CEFR progress per skill</span>
          </div>
          <div className="skill-analytics-rows">
            {Object.entries(skills).map(([skill, data]) => {
              const meta  = SKILL_META[skill] || { icon: null, label: skill }
              const level = data.level || 'A1'
              const score = data.score || 0
              const pct   = cefrProgress(level, score)
              const color = CEFR_COLOR[level] || 'var(--amber)'
              return (
                <div key={skill} className="skill-analytics-row">
                  <div className="skill-analytics-left">
                    <span style={{ color }}>{meta.icon}</span>
                    <span className="skill-analytics-name">{meta.label}</span>
                  </div>
                  <div className="skill-analytics-bar">
                    <div className="skill-analytics-fill" style={{ width: `${pct}%`, background: color }} />
                  </div>
                  <span className="skill-analytics-level" style={{ color }}>{level}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Vocabulary stats ── */}
      {!dashLoading && (
        <div className="card">
          <div className="analytics-header">
            <h3>Vocabulary</h3>
            {vocab.total_words > 0 && (
              <span className="small muted">{vocab.mastery_rate || 0}% mastered</span>
            )}
          </div>
          {vocab.total_words > 0 ? (
            <>
              <div className="vocab-stat-row">
                <div className="vocab-stat-item">
                  <span className="vocab-stat-n">{vocab.total_words}</span>
                  <span className="vocab-stat-l small muted">Total</span>
                </div>
                <div className="vocab-stat-item">
                  <span className="vocab-stat-n" style={{ color: 'var(--green)' }}>{vocab.mastered || 0}</span>
                  <span className="vocab-stat-l small muted">Mastered</span>
                </div>
                <div className="vocab-stat-item">
                  <span className="vocab-stat-n" style={{ color: 'var(--amber)' }}>{vocab.in_progress || 0}</span>
                  <span className="vocab-stat-l small muted">Learning</span>
                </div>
                {vocab.due_today > 0 && (
                  <div className="vocab-stat-item">
                    <span className="vocab-stat-n" style={{ color: 'var(--red)' }}>{vocab.due_today}</span>
                    <span className="vocab-stat-l small muted">Due today</span>
                  </div>
                )}
              </div>
              <div className="vocab-mastery-bar">
                <div className="vocab-mastery-fill" style={{ width: `${vocab.mastery_rate || 0}%` }} />
              </div>
            </>
          ) : (
            <p className="small muted">No vocabulary tracked yet. Start a session to build your word list.</p>
          )}
        </div>
      )}

      {/* ── Recent performance ── */}
      {!dashLoading && scoredSessions.length >= 2 && (
        <div className="card">
          <div className="analytics-header">
            <h3>Recent performance</h3>
            <span className="small muted">Last {scoredSessions.length} sessions</span>
          </div>
          <div className="perf-chart-row">
            <Sparkline sessions={recent} />
            <div className="perf-sessions-list">
              {recent.slice(0, 5).map((s, i) => {
                const sc = s.performance_score != null ? Math.round(s.performance_score) : null
                const c  = sc == null ? 'var(--text-muted)' : sc >= 75 ? 'var(--green)' : sc >= 50 ? 'var(--amber)' : 'var(--red)'
                const d  = parseUTC(s.date)
                return (
                  <div key={i} className="psession-row">
                    <span className="psession-date small muted">
                      {d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                    </span>
                    <span className="psession-type small muted">{s.session_type || 'mixed'}</span>
                    {sc != null && <span className="psession-score" style={{ color: c }}>{sc}<span style={{ color: 'var(--text-muted)', fontSize: '0.7em' }}>/100</span></span>}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── Error patterns ── */}
      {!dashLoading && errors.total_unresolved > 0 && (
        <div className="card">
          <div className="analytics-header">
            <h3>Areas to work on</h3>
            <span className="small muted">{errors.total_unresolved} open issue{errors.total_unresolved !== 1 ? 's' : ''}</span>
          </div>
          <div className="error-patterns">
            {(errors.recurring || []).slice(0, 5).map((err, i) => (
              <div key={i} className="error-pattern-row">
                <div>
                  <div className="epr-concept">{err.concept || err.category}</div>
                  <div className="epr-category small muted">{err.category}</div>
                </div>
                <span className="epr-count">×{err.count || err.occurrence_count || 1}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Languages ── */}
      <div className="card">
        <div className="languages-header">
          <h3>Languages</h3>
          <button className="btn btn-ghost btn-sm" onClick={() => setShowAddLang(v => !v)}>
            {showAddLang ? <X size={14} /> : <Plus size={14} />}
            {showAddLang ? 'Cancel' : 'Add language'}
          </button>
        </div>

        <div className="lang-profiles">
          {safeProfiles.length === 0 && <p className="small muted">No language profiles found.</p>}
          {safeProfiles.map(p => {
            const isActive = p.profile_id === profile?.profile_id
            return (
              <div key={p.profile_id} className={`lang-profile-card ${isActive ? 'active-lang' : ''}`}>
                <div className="lang-profile-left">
                  <span className="lang-flag">{LANG_FLAGS[p.target_language] || '🌐'}</span>
                  <div>
                    <div className="lang-profile-name">{LANG_LABELS[p.target_language] || p.target_language}</div>
                    <div className="small muted">
                      {p.overall_level === 'unassessed' ? 'Needs assessment' : (p.overall_level || 'Unassessed')}
                    </div>
                  </div>
                </div>
                <div className="lang-profile-right">
                  {isActive ? (
                    <span className="tag tag-amber" style={{ fontSize: '0.7rem' }}>
                      <CheckCircle size={10} /> Active
                    </span>
                  ) : (
                    <button className="btn btn-ghost btn-sm" onClick={() => handleSwitch(p)}>Switch</button>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {showAddLang && (
          <div className="add-lang-panel fade-in">
            <h3>Choose a language to add</h3>
            <p className="small muted">You'll take a placement assessment after adding.</p>
            <div className="add-lang-grid">
              {languages.filter(l => !existingLangs.has(l.key)).map(l => (
                <button
                  key={l.key}
                  className={`add-lang-btn ${selectedLang === l.key ? 'selected' : ''}`}
                  onClick={() => setSelectedLang(l.key)}
                  disabled={adding}
                >
                  <span style={{ fontSize: '1.3rem' }}>{LANG_FLAGS[l.key] || '🌐'}</span>
                  <span className="add-lang-name">{l.name}</span>
                  <span className="add-lang-native">{l.native_name}</span>
                </button>
              ))}
            </div>
            {addError && (
              <div className="error-msg mt-1" style={{ fontSize: '0.83rem', padding: '0.5rem 0.75rem' }}>
                {addError}
              </div>
            )}
            <button className="btn btn-primary" onClick={handleAddLanguage} disabled={!selectedLang || adding}>
              {adding ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <Plus size={15} />}
              {adding ? 'Adding…' : `Start learning ${LANG_LABELS[selectedLang] || selectedLang || '—'}`}
            </button>
          </div>
        )}
      </div>

      {/* ── Sign out ── */}
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <button className="btn btn-ghost" onClick={() => { logout(); navigate('/') }}>
          <LogOut size={15} /> Sign out
        </button>
      </div>
    </div>
  )
}
