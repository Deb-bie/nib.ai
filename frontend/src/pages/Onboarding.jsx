import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Globe, Target, ChevronRight, Eye, EyeOff } from 'lucide-react'
import { authService, profileService } from '../services/api'
import { useUser } from '../context/UserContext'
import NibLogo from '../components/shared/NibLogo'
import './Onboarding.css'

const GOALS = [
  { key: 'conversational', label: 'Everyday conversations', icon: '💬' },
  { key: 'travel',         label: 'Travel',                 icon: '✈️' },
  { key: 'business',       label: 'Business & work',        icon: '💼' },
  { key: 'academic',       label: 'Academic study',         icon: '🎓' },
]

const NATIVE_LANGUAGES = [
  'english', 'spanish', 'french', 'german', 'portuguese',
  'mandarin', 'japanese', 'arabic', 'hindi', 'russian',
]

// Fallback used if the backend isn't reachable yet
const FALLBACK_LANGUAGES = [
  { key: 'spanish',    name: 'Spanish',    native_name: 'Español'   },
  { key: 'french',     name: 'French',     native_name: 'Français'  },
  { key: 'german',     name: 'German',     native_name: 'Deutsch'   },
  { key: 'italian',    name: 'Italian',    native_name: 'Italiano'  },
  { key: 'portuguese', name: 'Portuguese', native_name: 'Português' },
  { key: 'mandarin',   name: 'Mandarin',   native_name: '普通话'     },
]

/** Map backend HTTP errors to plain-English messages */
function mapError(e) {
  const status = e.response?.status
  const detail = (e.response?.data?.detail || '').toLowerCase()
  if (status === 409) {
    if (detail.includes('email')) return 'An account with this email already exists. Try signing in instead.'
    if (detail.includes('username')) return 'That username is already taken. Please choose a different one.'
    return 'An account already exists with those details.'
  }
  if (status === 400) {
    if (detail.includes('language')) return 'The selected language is not currently supported.'
    return 'Please check your details and try again.'
  }
  if (status === 422) return 'Please fill in all required fields correctly.'
  if (status === 500) return 'Something went wrong on our end. Please try again in a moment.'
  return 'Something went wrong. Please try again.'
}

export default function Onboarding() {
  const navigate = useNavigate()
  const { login } = useUser()

  const [step, setStep] = useState(1) // 1 = account, 2 = language, 3 = goal
  const [languages, setLanguages] = useState(FALLBACK_LANGUAGES)
  const [langsLoading, setLangsLoading] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    native_language: 'english',
    target_language: '',
    learning_goal: 'conversational',
  })

  useEffect(() => {
    profileService.languages()
      .then(d => {
        const list = d.languages || []
        if (list.length > 0) setLanguages(list)
      })
      .catch(() => {
        // Backend unreachable — keep FALLBACK_LANGUAGES already in state
      })
      .finally(() => setLangsLoading(false))
  }, [])

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  
  const step1Valid = form.username.trim().length >= 2
    && form.email.includes('@')
    && form.password.length >= 8
    && form.password === form.confirmPassword

  const passwordMismatch = form.confirmPassword.length > 0
    && form.password !== form.confirmPassword

  const handleStep1Next = () => {
    if (!step1Valid) return
    setError('')
    setStep(2)
  }

  
  const handleSubmit = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await authService.register({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        native_language: form.native_language,
        target_language: form.target_language,
        learning_goal: form.learning_goal,
      })
      const profileData = {
        profile_id: res.profile_id,
        target_language: res.target_language,
        overall_level: 'A1',
      }
      login(
        { username: res.username, email: form.email.trim(), user_id: res.user_id },
        profileData,
        [profileData],
      )
      navigate('/dashboard')
    } catch (e) {
      setError(mapError(e))
      setLoading(false)
    }
  }

  return (
    <div className="onboarding">
      {/* Background decoration */}
      <div className="onboarding-bg">
        <div className="bg-orb bg-orb-1" />
        <div className="bg-orb bg-orb-2" />
      </div>

      <div className="onboarding-container fade-up">
        {/* Header */}
        <div className="onboarding-header">
          <div className="brand-mark">
            <NibLogo size="2rem" />
          </div>
          <p>Your personal language tutor, powered by AI</p>
          <p className="mt-2" style={{ fontSize: '0.82rem' }}>
            Already have an account?{' '}
            <Link to="/login" className="amber">Sign in</Link>
          </p>
        </div>

        {/* Step indicator */}
        <div className="step-indicator">
          {[1, 2, 3].map(n => (
            <div key={n} className={`step-dot ${step >= n ? 'active' : ''}`} />
          ))}
        </div>

        {/* Step 1 — Account */}
        {step === 1 && (
          <div className="onboarding-card fade-up">
            <h2>Create your account</h2>
            <p className="mt-1">Set up your credentials to keep your progress safe.</p>

            <div className="form-fields mt-3">
              <div className="field">
                <label>Username</label>
                <input
                  type="text"
                  placeholder="e.g. alex_learns"
                  value={form.username}
                  onChange={e => set('username', e.target.value)}
                  autoFocus
                />
              </div>
              <div className="field">
                <label>Email</label>
                <input
                  type="email"
                  placeholder="you@example.com"
                  value={form.email}
                  onChange={e => set('email', e.target.value)}
                />
              </div>
              <div className="field">
                <label>Password</label>
                <div className="input-with-icon">
                  <input
                    type={showPw ? 'text' : 'password'}
                    placeholder="At least 8 characters"
                    value={form.password}
                    onChange={e => set('password', e.target.value)}
                  />
                  <button
                    type="button"
                    className="input-icon-btn"
                    onClick={() => setShowPw(v => !v)}
                    tabIndex={-1}
                  >
                    {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
                {form.password.length > 0 && form.password.length < 8 && (
                  <p className="field-hint field-hint-warn">Must be at least 8 characters</p>
                )}
              </div>
              <div className="field">
                <label>Confirm password</label>
                <div className="input-with-icon">
                  <input
                    type={showConfirm ? 'text' : 'password'}
                    placeholder="Re-enter your password"
                    value={form.confirmPassword}
                    onChange={e => set('confirmPassword', e.target.value)}
                  />
                  <button
                    type="button"
                    className="input-icon-btn"
                    onClick={() => setShowConfirm(v => !v)}
                    tabIndex={-1}
                  >
                    {showConfirm ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
                {passwordMismatch && (
                  <p className="field-hint field-hint-warn">Passwords don't match</p>
                )}
              </div>
              <div className="field">
                <label>Your native language</label>
                <select value={form.native_language} onChange={e => set('native_language', e.target.value)}>
                  {NATIVE_LANGUAGES.map(l => (
                    <option key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</option>
                  ))}
                </select>
              </div>
            </div>

            {error && <div className="error-msg mt-2">{error}</div>}

            <button
              className="btn btn-primary btn-full mt-3"
              onClick={handleStep1Next}
              disabled={!step1Valid}
            >
              Continue <ChevronRight size={16} />
            </button>
          </div>
        )}

        {/* Step 2 — Language */}
        {step === 2 && (
          <div className="onboarding-card fade-up">
            <div className="step-back" onClick={() => setStep(1)}>← Back</div>
            <Globe size={28} className="amber" />
            <h2 className="mt-2">What are you learning?</h2>
            <p className="mt-1">Choose the language you want to master.</p>

            {langsLoading ? (
              <div className="langs-loading mt-3">
                <span className="spinner" />
                <span>Loading languages…</span>
              </div>
            ) : (
              <div className="language-grid mt-3">
                {languages.map(lang => (
                  <button
                    key={lang.key}
                    className={`lang-option ${form.target_language === lang.key ? 'selected' : ''}`}
                    onClick={() => set('target_language', lang.key)}
                  >
                    <span className="lang-name">{lang.name}</span>
                    <span className="lang-native">{lang.native_name}</span>
                  </button>
                ))}
              </div>
            )}

            <button
              className="btn btn-primary btn-full mt-3"
              onClick={() => setStep(3)}
              disabled={!form.target_language || langsLoading}
            >
              Continue <ChevronRight size={16} />
            </button>
          </div>
        )}

        {/* Step 3 — Goal */}
        {step === 3 && (
          <div className="onboarding-card fade-up">
            <div className="step-back" onClick={() => setStep(2)}>← Back</div>
            <Target size={28} className="amber" />
            <h2 className="mt-2">What's your goal?</h2>
            <p className="mt-1">This shapes how your tutor teaches you.</p>

            <div className="goal-grid mt-3">
              {GOALS.map(g => (
                <button
                  key={g.key}
                  className={`goal-option ${form.learning_goal === g.key ? 'selected' : ''}`}
                  onClick={() => set('learning_goal', g.key)}
                >
                  <span className="goal-icon">{g.icon}</span>
                  <span>{g.label}</span>
                </button>
              ))}
            </div>

            {error && <div className="error-msg mt-2">{error}</div>}

            <button
              className="btn btn-primary btn-full mt-3"
              onClick={handleSubmit}
              disabled={loading}
            >
              {loading ? <span className="spinner" /> : <>Start learning <ChevronRight size={16} /></>}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
