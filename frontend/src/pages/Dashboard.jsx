import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Play, BookOpen, Clock, Target, Lock, Brain, AlertCircle, ChevronRight } from 'lucide-react'
import { profileService, progressService } from '../services/api'
import { useUser } from '../context/UserContext'
import { LANG_FLAGS, LANG_LABELS } from '../utils/languages'
import './Dashboard.css'

const LEVEL_COLORS = { A1:'#5a9e6f', A2:'#4a7fb5', B1:'#e8a838', B2:'#c48a20', C1:'#c0533a', C2:'#8b4fff' }

export default function Dashboard() {
  const { profile, user } = useUser()
  const navigate = useNavigate()
  const [data, setData]       = useState(null)
  const [plan, setPlan]       = useState(undefined)  // undefined=loading, null=none, obj=loaded
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!profile) { navigate('/'); return }

    setLoading(true)
    setData(null)
    setPlan(undefined)
    Promise.all([
      profileService.dashboard(profile.profile_id).catch(() => null),
      progressService.plan(profile.profile_id).catch(() => null),
    ]).then(([dashData, planData]) => {
      setData(dashData)
      setPlan(planData?.plan ?? null)
    }).finally(() => setLoading(false))
  }, [profile?.profile_id]) // re-fetch when the active language changes

  if (loading) return (
    <div className="dashboard-loading">
      <span className="spinner" />
    </div>
  )

  const learner  = data?.learner || {}
  const sessions = data?.recent_sessions || []
  const skills   = learner.skills || {}
  const errors   = data?.errors || {}
  const vocab    = data?.vocabulary || {}

  const isA1Beginner = !learner.overall_level || learner.overall_level === 'A1'
  const hasNoSessions = (learner.sessions_completed || 0) === 0

  return (
    <div className="dashboard">
      {/* ── Welcome ── */}
      <div className="dash-hero fade-up">
        <div>
          <h1>Good to see you, <span className="amber">{user?.username}</span></h1>
          <p className="mt-1">
            {LANG_FLAGS[learner.target_language] || '🌐'}{' '}
            Learning <span style={{ textTransform:'capitalize' }}>
              {LANG_LABELS[learner.target_language] || learner.target_language}
            </span>
            {' '}· <span className="amber">{learner.streak_days || 0} day streak</span>
            {' '}· {learner.sessions_completed || 0} sessions completed
          </p>
        </div>
        <button className="btn btn-primary start-btn" onClick={() => navigate('/session')}>
          <Play size={16} /> Start session
        </button>
      </div>

      {/* ── Overall level ── */}
      <div className="dash-level-row fade-up" style={{ animationDelay: '0.05s' }}>
        <div className="card level-card">
          <span className="level-pill" style={{ color: LEVEL_COLORS[learner.overall_level] || LEVEL_COLORS['A1'] }}>
            {learner.overall_level || 'A1'}
          </span>
          {isA1Beginner && hasNoSessions ? (
            <p className="small muted mt-1" style={{ textAlign: 'center', lineHeight: 1.4 }}>
              You're starting as a beginner — your level will rise as you practise!
            </p>
          ) : (
            <p className="small muted mt-1">Overall level</p>
          )}
        </div>
        <div className="card stat-card">
          <Clock size={18} className="amber" />
          <span className="stat-n">{Math.round((learner.total_minutes_studied || 0) / 60)}h</span>
          <p className="small muted">Total study time</p>
        </div>
        <div className="card stat-card">
          <BookOpen size={18} className="amber" />
          <span className="stat-n">{vocab.total_words || 0}</span>
          <p className="small muted">Words tracked</p>
        </div>
        <div className="card stat-card">
          <Target size={18} className="amber" />
          <span className="stat-n">{vocab.due_today || 0}</span>
          <p className="small muted">Reviews due today</p>
        </div>
      </div>

      {/* ── Curriculum Planner ── */}
      <CurriculumPlanCard plan={plan} isNewLearner={isA1Beginner && hasNoSessions} />

      {/* ── Skills ── */}
      {Object.keys(skills).length > 0 && (
        <div className="card fade-up" style={{ animationDelay: '0.1s' }}>
          <h3>Skill breakdown</h3>
          <div className="skills-grid mt-2">
            {Object.entries(skills).map(([skill, sd]) => (
              <div key={skill} className="skill-row">
                <span className="skill-name">{skill}</span>
                <div className="skill-bar-wrap">
                  <div className="progress-bar">
                    <div
                      className="progress-bar-fill"
                      style={{ width: `${(sd.score / 100) * 100}%`,
                               background: LEVEL_COLORS[sd.level] || 'var(--amber)' }}
                    />
                  </div>
                </div>
                <span className="skill-level tag tag-muted">{sd.level}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Recent sessions ── */}
      {sessions.length > 0 && (
        <div className="card fade-up" style={{ animationDelay: '0.15s' }}>
          <div className="flex" style={{ justifyContent: 'space-between' }}>
            <h3>Recent sessions</h3>
            <Link to="/history" className="small amber">View all →</Link>
          </div>
          <div className="sessions-list mt-2">
            {sessions.slice(0, 4).map(s => (
              <div key={s.session_id} className="session-row">
                <div>
                  <span className="small" style={{ textTransform:'capitalize' }}>{s.session_type}</span>
                  <span className="small muted"> · {s.duration_minutes}m</span>
                </div>
                <div className="session-score-wrap">
                  <span
                    className="session-score"
                    style={{ color: s.performance_score >= 70 ? 'var(--green)' : s.performance_score >= 40 ? 'var(--amber)' : 'var(--red)' }}
                  >
                    {Math.round(s.performance_score || 0)}
                  </span>
                  <span className="small muted">/100</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Recurring errors ── */}
      {errors.recurring?.length > 0 && (
        <div className="card fade-up" style={{ animationDelay: '0.2s' }}>
          <h3>Areas to work on</h3>
          <div className="error-list mt-2">
            {errors.recurring.slice(0, 4).map((e, i) => (
              <div key={i} className="error-row">
                <div>
                  <span className="small">{e.concept.replace(/_/g, ' ')}</span>
                  <span className="small muted"> · {e.category.replace(/_/g, ' ')}</span>
                </div>
                <span className="tag tag-red">{e.occurrences}×</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}



function CurriculumPlanCard({ plan, isNewLearner }) {
  const navigate = useNavigate()

  // ── No plan yet ──
  if (!plan) {
    return (
      <div className="card curriculum-card fade-up locked-card" style={{ animationDelay: '0.08s' }}>
        <div className="curriculum-header">
          <div className="curriculum-title">
            <Brain size={17} className="amber" />
            <h3>Your Curriculum Plan</h3>
          </div>
          <span className="locked-badge">
            <Lock size={11} /> {isNewLearner ? 'Unlocks after your first session' : 'No plan yet'}
          </span>
        </div>

        {/* Preview skeleton */}
        <div className="curriculum-preview mt-2">
          <p className="small muted" style={{ marginBottom: '1rem' }}>
            {isNewLearner
              ? 'After your first session, the AI tutor will build a personalised curriculum just for you — deciding exactly what to teach, in what order, and why.'
              : 'Complete a session and the AI tutor will build a personalised curriculum plan based on your progress.'}
          </p>

          <div className="preview-focus">
            {['Vocabulary', 'Grammar', 'Conversation'].map((label, i) => (
              <div key={label} className="focus-preview-row">
                <span className="focus-preview-label muted">{label}</span>
                <div className="progress-bar" style={{ flex: 1 }}>
                  <div className="progress-bar-fill locked-bar" style={{ width: `${[40, 35, 25][i]}%` }} />
                </div>
                <span className="focus-preview-pct muted">?%</span>
              </div>
            ))}
          </div>

          <div className="preview-concepts mt-2">
            {['Priority concepts', 'Weak spots', 'Agent\'s reasoning'].map(label => (
              <div key={label} className="concept-placeholder">
                <span className="concept-lock-icon"><Lock size={10} /></span>
                <span className="small muted">{label}</span>
              </div>
            ))}
          </div>

          {isNewLearner && (
            <button
              className="btn btn-primary btn-full mt-3"
              style={{ justifyContent: 'center' }}
              onClick={() => navigate('/session')}
            >
              Start your first session <ChevronRight size={15} />
            </button>
          )}
        </div>
      </div>
    )
  }

  // ── Active plan ──
  const focus    = plan.session_focus || {}
  const reasoning = plan.agent_reasoning || ''


  const toLabel = (item) => {
    if (!item) return ''
    if (typeof item === 'string') return item
    // Object shapes the planner produces
    return item.concept || item.issue || item.skill || item.name
      || Object.values(item).find(v => typeof v === 'string') || JSON.stringify(item)
  }
  const concepts = (plan.priority_concepts || []).map(toLabel).filter(Boolean)
  const issues   = (plan.detected_issues   || []).map(toLabel).filter(Boolean)
  const planDate = plan.created_at
    ? new Date(plan.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : null

  return (
    <div className="card curriculum-card fade-up" style={{ animationDelay: '0.08s' }}>
      <div className="curriculum-header">
        <div className="curriculum-title">
          <Brain size={17} className="amber" />
          <h3>Your Curriculum Plan</h3>
        </div>
        {planDate && <span className="plan-date small muted">Updated {planDate}</span>}
      </div>

      {/* Session focus breakdown */}
      {Object.keys(focus).length > 0 && (
        <div className="curriculum-focus mt-2">
          {Object.entries(focus).map(([k, v]) => (
            <div key={k} className="focus-row">
              <span className="focus-label-sm">{k}</span>
              <div className="progress-bar" style={{ flex: 1 }}>
                <div
                  className="progress-bar-fill"
                  style={{ width: `${v}%` }}
                />
              </div>
              <span className="focus-pct-sm">{v}%</span>
            </div>
          ))}
        </div>
      )}

      {/* Priority concepts */}
      {concepts.length > 0 && (
        <div className="curriculum-concepts mt-2">
          <p className="small muted" style={{ marginBottom: '0.4rem' }}>Priority concepts</p>
          <div className="concept-tags">
            {concepts.map((c, i) => (
              <span key={i} className="tag tag-amber concept-tag">{c}</span>
            ))}
          </div>
        </div>
      )}

      {/* Detected issues */}
      {issues.length > 0 && (
        <div className="curriculum-issues mt-2">
          <p className="small muted" style={{ marginBottom: '0.4rem' }}>
            <AlertCircle size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
            Needs attention
          </p>
          <div className="concept-tags">
            {issues.map((issue, i) => (
              <span key={i} className="tag tag-red concept-tag">{issue}</span>
            ))}
          </div>
        </div>
      )}

      {/* Agent reasoning */}
      {reasoning && (
        <div className="curriculum-reasoning mt-2">
          <p className="small muted reasoning-label">Agent's reasoning</p>
          <p className="small reasoning-text">"{reasoning}"</p>
        </div>
      )}
    </div>
  )
}
