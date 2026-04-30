import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { LogIn, Eye, EyeOff } from 'lucide-react'
import { authService } from '../services/api'
import { useUser } from '../context/UserContext'
import NibLogo from '../components/shared/NibLogo'
import './Login.css'

/** Map backend HTTP errors to plain-English messages */
function mapError(e) {
  const status = e.response?.status
  const detail = (e.response?.data?.detail || '').toLowerCase()
  if (status === 401) {
    if (detail.includes('email') || detail.includes('no account')) return 'No account found with that email address.'
    if (detail.includes('password') || detail.includes('incorrect')) return 'Incorrect password. Please try again.'
    return 'Incorrect email or password. Please try again.'
  }
  if (status === 404) return 'No account found with that email address.'
  if (status === 422) return 'Please fill in both your email and password.'
  if (status === 500) return 'Something went wrong on our end. Please try again in a moment.'
  return 'Sign in failed. Please check your details and try again.'
}

export default function Login() {
  const navigate = useNavigate()
  const { login } = useUser()

  const [form, setForm] = useState({ email: '', password: '' })
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleLogin = async () => {
    setError('')
    setLoading(true)
    try {
      const res = await authService.login(form.email, form.password)

      const profile = res.profiles?.[0]
      if (!profile) {
        setError('No language profile found. Please sign up first.')
        setLoading(false)
        return
      }

      const allProfiles = (res.profiles || []).map(p => ({
        profile_id: p.profile_id,
        target_language: p.target_language,
        overall_level: p.overall_level,
      }))
      login(
        { username: res.username, email: res.email, user_id: res.user_id },
        {
          profile_id: profile.profile_id,
          target_language: profile.target_language,
          overall_level: profile.overall_level,
        },
        allProfiles,
      )
      navigate('/dashboard')
    } catch (e) {
      setError(mapError(e))
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && form.email && form.password) handleLogin()
  }

  return (
    <div className="login-page">
      <div className="login-bg">
        <div className="bg-orb bg-orb-1" />
        <div className="bg-orb bg-orb-2" />
      </div>

      <div className="login-container fade-up">
        <div className="login-header">
          <div className="brand-mark">
            <NibLogo size="2rem" />
          </div>
          <p>Welcome back</p>
        </div>

        <div className="login-card card">
          <div className="login-fields">
            <div className="field">
              <label>Email</label>
              <input
                type="email"
                placeholder="you@example.com"
                value={form.email}
                onChange={e => set('email', e.target.value)}
                onKeyDown={handleKey}
                autoFocus
              />
            </div>
            <div className="field">
              <label>Password</label>
              <div className="input-with-icon">
                <input
                  type={showPw ? 'text' : 'password'}
                  placeholder="Your password"
                  value={form.password}
                  onChange={e => set('password', e.target.value)}
                  onKeyDown={handleKey}
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
            </div>
          </div>

          {error && <div className="login-error">{error}</div>}

          <button
            className="btn btn-primary btn-full mt-3"
            onClick={handleLogin}
            disabled={loading || !form.email || !form.password}
          >
            {loading
              ? <span className="spinner" />
              : <><LogIn size={16} /> Sign in</>
            }
          </button>

          <p className="login-footer mt-3 small muted">
            New to nib.ai?{' '}
            <Link to="/" className="amber">Create an account</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
