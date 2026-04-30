import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer,
         LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { progressService } from '../services/api'
import { useUser } from '../context/UserContext'
import './Progress.css'

const TABS = ['Skills', 'Errors', 'Agent plan']

export default function Progress() {
  const { profile } = useUser()
  const navigate = useNavigate()
  const [tab, setTab] = useState('Skills')
  const [skills, setSkills] = useState(null)
  const [errors, setErrors] = useState(null)
  const [plan, setPlan] = useState(null)
  const [vocab, setVocab] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!profile) { navigate('/'); return }
    const id = profile.profile_id
    Promise.all([
      progressService.skills(id),
      progressService.errors(id),
      progressService.plan(id),
      progressService.vocabulary(id),
    ]).then(([s, e, p, v]) => {
      setSkills(s)
      setErrors(e)
      setPlan(p)
      setVocab(v)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div style={{ display:'flex', justifyContent:'center', alignItems:'center', minHeight:'60vh' }}>
      <span className="spinner" />
    </div>
  )

  const radarData = skills?.skills
    ? Object.entries(skills.skills).map(([skill, d]) => ({
        skill: skill.charAt(0).toUpperCase() + skill.slice(1),
        score: d.score,
        fullMark: 100,
      }))
    : []

  return (
    <div className="progress-page">
      <div className="progress-header fade-up">
        <div>
          <h2>Progress</h2>
          <p>Your complete learning history and what your tutor is planning next.</p>
        </div>
        <span className="tag tag-amber" style={{ fontSize:'0.85rem', padding:'0.35rem 0.85rem' }}>
          {skills?.overall_level || '—'} overall
        </span>
      </div>

      {/* Tabs */}
      <div className="progress-tabs fade-up">
        {TABS.map(t => (
          <button
            key={t}
            className={`tab-btn ${tab === t ? 'active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── Skills tab ── */}
      {tab === 'Skills' && (
        <div className="tab-content fade-up">
          <div className="skills-split">
            {/* Radar chart */}
            <div className="card radar-card">
              <h3>Skill radar</h3>
              <ResponsiveContainer width="100%" height={260}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#2e2c27" />
                  <PolarAngleAxis
                    dataKey="skill"
                    tick={{ fill: '#8a8070', fontSize: 11 }}
                  />
                  <Radar
                    dataKey="score"
                    stroke="#e8a838"
                    fill="#e8a838"
                    fillOpacity={0.15}
                    strokeWidth={2}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* Skill list */}
            <div className="card skill-list-card">
              <h3>Per-skill levels</h3>
              <div className="skill-rows mt-2">
                {skills?.skills && Object.entries(skills.skills).map(([skill, d]) => (
                  <div key={skill} className="skill-detail-row">
                    <div className="skill-detail-top">
                      <span className="skill-detail-name">{skill}</span>
                      <span className="skill-detail-level tag tag-amber">{d.level}</span>
                    </div>
                    <div className="progress-bar mt-1">
                      <div className="progress-bar-fill" style={{ width: `${d.score}%` }} />
                    </div>
                    <span className="skill-detail-score small muted">{d.score}/100 within {d.level}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Vocab stats */}
          {vocab && (
            <div className="card vocab-card mt-0">
              <h3>Vocabulary</h3>
              <div className="vocab-stats mt-2">
                <div className="vocab-stat">
                  <span className="vocab-n">{vocab.stats?.total_words || 0}</span>
                  <span className="small muted">Total words</span>
                </div>
                <div className="vocab-stat">
                  <span className="vocab-n green">{vocab.stats?.mastered || 0}</span>
                  <span className="small muted">Mastered</span>
                </div>
                <div className="vocab-stat">
                  <span className="vocab-n amber">{vocab.stats?.due_today || 0}</span>
                  <span className="small muted">Due today</span>
                </div>
                <div className="vocab-stat">
                  <span className="vocab-n">{vocab.stats?.mastery_rate || 0}%</span>
                  <span className="small muted">Mastery rate</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Errors tab ── */}
      {tab === 'Errors' && (
        <div className="tab-content fade-up">
          <div className="card">
            <h3>Recurring mistakes</h3>
            <p className="mt-1 small muted">
              These concepts have appeared multiple times.
              Your tutor is actively targeting them.
            </p>
            {errors?.recurring?.length > 0 ? (
              <div className="error-cards mt-2">
                {errors.recurring.map((e, i) => (
                  <div key={i} className="error-card">
                    <div className="error-card-top">
                      <span className="error-concept">{e.concept.replace(/_/g, ' ')}</span>
                      <span className="tag tag-red">{e.occurrences}×</span>
                    </div>
                    <span className="tag tag-muted mt-1" style={{ textTransform:'capitalize' }}>
                      {e.category.replace(/_/g, ' ')}
                    </span>
                    <div className="error-example mt-1">
                      <span className="small muted">You said: </span>
                      <span className="small red">"{e.example}"</span>
                      <span className="small muted"> → </span>
                      <span className="small green">"{e.correct_form}"</span>
                    </div>
                    {e.needs_strategy_switch && (
                      <div className="strategy-switch-badge mt-1">
                        ⚠ Tutor switching teaching strategy
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-2 muted small">No recurring errors yet — keep practising!</p>
            )}
          </div>
        </div>
      )}

      {/* ── Agent plan tab ── */}
      {tab === 'Agent plan' && (
        <div className="tab-content fade-up">
          {plan?.plan ? (
            <>
              {/* The money shot — agent's reasoning made visible */}
              <div className="card reasoning-card">
                <div className="reasoning-label">
                  <span>🧠</span>
                  <span>Why your tutor chose this plan</span>
                </div>
                <p className="reasoning-text mt-2">{plan.plan.agent_reasoning}</p>
              </div>

              <div className="plan-split">
                {/* Session focus */}
                <div className="card">
                  <h3>Next session focus</h3>
                  <div className="focus-bars mt-2">
                    {Object.entries(plan.plan.session_focus || {}).map(([k, v]) => (
                      <div key={k} className="focus-bar-row">
                        <span className="focus-bar-label">{k}</span>
                        <div className="progress-bar">
                          <div className="progress-bar-fill" style={{ width: `${v}%` }} />
                        </div>
                        <span className="focus-bar-pct small muted">{v}%</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Priority concepts */}
                <div className="card">
                  <h3>Priority concepts</h3>
                  {plan.plan.priority_concepts?.length > 0 ? (
                    <div className="priority-list mt-2">
                      {plan.plan.priority_concepts.map((c, i) => (
                        <div key={i} className="priority-item">
                          <div className="flex gap-1">
                            <span className="tag tag-amber">{c.skill}</span>
                            <span className="small">{c.concept?.replace(/_/g,' ')}</span>
                          </div>
                          <p className="small muted mt-1">{c.reason}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="small muted mt-2">No specific concepts prioritised.</p>
                  )}
                </div>
              </div>

              {/* Detected issues */}
              {plan.plan.detected_issues?.length > 0 && (
                <div className="card">
                  <h3>Issues detected</h3>
                  <div className="issue-list mt-2">
                    {plan.plan.detected_issues.map((issue, i) => (
                      <div key={i} className="issue-item">
                        <span className="tag tag-red">{issue.type}</span>
                        <p className="small muted mt-1">{issue.detail}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Strategy overrides */}
              {Object.keys(plan.plan.strategy_overrides || {}).length > 0 && (
                <div className="card">
                  <h3>Teaching strategy changes</h3>
                  <p className="small muted mt-1">Concepts where drills weren't working — new approach:</p>
                  <div className="strategy-list mt-2">
                    {Object.entries(plan.plan.strategy_overrides).map(([concept, strategy]) => (
                      <div key={concept} className="strategy-item">
                        <span className="small">{concept.replace(/_/g,' ')}</span>
                        <span className="tag tag-green">{strategy}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="card">
              <p className="muted">No curriculum plan yet — complete your placement assessment first.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
