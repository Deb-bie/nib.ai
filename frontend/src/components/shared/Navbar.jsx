import { useState, useRef, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  BarChart2, MessageCircle, Sun, Moon,
  Dumbbell, Clock, ChevronDown, User, LayoutDashboard,
} from 'lucide-react'
import { useUser } from '../../context/UserContext'
import { useTheme } from '../../context/ThemeContext'
import NibLogo from './NibLogo'
import { LANG_FLAGS, LANG_LABELS } from '../../utils/languages'
import './Navbar.css'

const NAV_LINKS = [
  { to: '/dashboard', icon: <LayoutDashboard size={20} />, label: 'Home'     },
  { to: '/session',   icon: <MessageCircle   size={20} />, label: 'Session'  },
  { to: '/practice',  icon: <Dumbbell        size={20} />, label: 'Practice' },
  { to: '/progress',  icon: <BarChart2       size={20} />, label: 'Progress' },
  { to: '/history',   icon: <Clock           size={20} />, label: 'History'  },
]

export default function Navbar() {
  const { user, profile, allProfiles, switchProfile } = useUser()
  const { theme, toggle } = useTheme()
  const location = useLocation()
  const navigate  = useNavigate()

  const [langOpen, setLangOpen] = useState(false)
  const dropRef = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if (dropRef.current && !dropRef.current.contains(e.target)) setLangOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleSwitch = (p) => {
    setLangOpen(false)
    switchProfile(p)
    navigate('/dashboard')
  }

  const otherProfiles = (allProfiles || []).filter(p => p.profile_id !== profile?.profile_id)
  const isActive = (to) => location.pathname === to

  return (
    <>
      {/* ── Top bar ── */}
      <nav className="navbar">
        <Link to="/dashboard" className="navbar-brand">
          <NibLogo size="1.15rem" />
        </Link>

        {/* Desktop nav links */}
        <div className="navbar-links desktop-only">
          {NAV_LINKS.map(link => (
            <Link
              key={link.to}
              to={link.to}
              className={`nav-link ${isActive(link.to) ? 'active' : ''}`}
            >
              {link.icon}
              {link.label}
            </Link>
          ))}
        </div>

        <div className="navbar-right">
          {/* Language switcher */}
          {profile && (
            <div className="lang-switcher" ref={dropRef}>
              <button
                className="lang-switcher-btn"
                onClick={() => setLangOpen(v => !v)}
                title="Switch language"
              >
                <span className="nav-lang-flag">{LANG_FLAGS[profile.target_language] || '🌐'}</span>
                <span className="nav-lang tag tag-amber">
                  {LANG_LABELS[profile.target_language] || profile.target_language}
                </span>
                {otherProfiles.length > 0 && <ChevronDown size={11} className="lang-chevron" />}
              </button>

              {langOpen && (
                <div className="lang-dropdown fade-in">
                  {otherProfiles.length > 0 && (
                    <>
                      <p className="lang-dropdown-label small muted">Switch to</p>
                      {otherProfiles.map(p => (
                        <button key={p.profile_id} className="lang-dropdown-item" onClick={() => handleSwitch(p)}>
                          <span className="lang-dropdown-flag">{LANG_FLAGS[p.target_language] || '🌐'}</span>
                          <span style={{ textTransform: 'capitalize' }}>
                            {LANG_LABELS[p.target_language] || p.target_language}
                          </span>
                          <span className="small muted">{p.overall_level === 'unassessed' ? 'New' : (p.overall_level || '—')}</span>
                        </button>
                      ))}
                      <div className="lang-dropdown-divider" />
                    </>
                  )}
                  <Link
                    to="/profile"
                    className="lang-dropdown-item lang-add-link"
                    onClick={() => setLangOpen(false)}
                  >
                    + Add language
                  </Link>
                </div>
              )}
            </div>
          )}

          {/* Profile link — desktop only */}
          {user && (
            <Link to="/profile" className="nav-user-btn desktop-only" title="Your profile">
              <User size={13} />
              <span className="nav-user">{user.username}</span>
            </Link>
          )}

          {/* Theme toggle */}
          <button
            onClick={toggle}
            className="btn btn-ghost btn-sm theme-toggle"
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </div>
      </nav>

      {/* ── Mobile bottom tab bar ── */}
      <nav className="bottom-nav mobile-only" aria-label="Main navigation">
        {NAV_LINKS.map(link => (
          <Link
            key={link.to}
            to={link.to}
            className={`bottom-nav-item ${isActive(link.to) ? 'active' : ''}`}
          >
            {link.icon}
            <span className="bottom-nav-label">{link.label}</span>
          </Link>
        ))}
        <Link
          to="/profile"
          className={`bottom-nav-item ${isActive('/profile') ? 'active' : ''}`}
        >
          <User size={20} />
          <span className="bottom-nav-label">Profile</span>
        </Link>
      </nav>
    </>
  )
}
