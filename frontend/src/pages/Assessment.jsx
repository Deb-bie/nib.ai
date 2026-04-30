import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Send, ChevronRight } from 'lucide-react'
import { profileService } from '../services/api'
import { useUser } from '../context/UserContext'
import './Assessment.css'

export default function Assessment() {
  const { profile, updateProfile } = useUser()
  const navigate = useNavigate()
  const messagesEndRef = useRef(null)

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [thinking, setThinking] = useState(false)
  const [complete, setComplete] = useState(false)
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (!profile) { navigate('/'); return }
    startAssessment()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  const addMessage = (role, content) => {
    setMessages(prev => [...prev, { id: Date.now() + Math.random(), role, content }])
  }

  const startAssessment = async () => {
    try {
      const res = await profileService.startAssessment(profile.profile_id)
      addMessage('assistant', res.opening_message)
    } catch {
      addMessage('system', 'Could not start assessment. Please check your connection.')
    } finally {
      setLoading(false)
    }
  }

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || thinking) return
    setInput('')
    addMessage('user', text)
    setThinking(true)
    try {
      const res = await profileService.sendAssessmentMessage(profile.profile_id, text)
      addMessage('assistant', res.reply)
      if (res.is_complete) {
        setComplete(true)
        setResult(res.result)
        updateProfile({ overall_level: res.result?.overall_level })
      }
    } catch {
      addMessage('system', 'Something went wrong. Please try again.')
    } finally {
      setThinking(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  return (
    <div className="assessment">
      <div className="assessment-container">
        <div className="assessment-header fade-up">
          <h2>Placement Assessment</h2>
          <p>Have a short conversation so your tutor can understand your level.</p>
        </div>

        <div className="assessment-chat card fade-up">
          {loading && (
            <div className="flex gap-1 muted small" style={{ padding: '1rem' }}>
              <span className="spinner" /> Starting assessment...
            </div>
          )}

          <div className="assessment-messages">
            {messages.map(msg => (
              <div key={msg.id} className={`amsg amsg-${msg.role} fade-up`}>
                {msg.role === 'assistant' && <span className="amsg-label">Tutor</span>}
                {msg.role === 'user'      && <span className="amsg-label">You</span>}
                <div className="amsg-content">{msg.content}</div>
              </div>
            ))}
            {thinking && (
              <div className="amsg amsg-assistant fade-in">
                <span className="amsg-label">Tutor</span>
                <div className="amsg-content thinking-dots">
                  <span/><span/><span/>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Result */}
          {complete && result && (
            <div className="assessment-result fade-up">
              <div className="result-level">
                <span className="level-badge">{result.overall_level}</span>
              </div>
              <p>Your overall level is <strong className="amber">{result.overall_level}</strong>.</p>
              <p className="mt-1 small muted">{result.reasoning}</p>
              <button
                className="btn btn-primary mt-3"
                onClick={() => navigate('/dashboard')}
              >
                Start learning <ChevronRight size={16} />
              </button>
            </div>
          )}

          {/* Input */}
          {!complete && !loading && (
            <div className="assessment-input">
              <input
                type="text"
                placeholder="Reply in the target language..."
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKey}
                disabled={thinking}
              />
              <button
                className="btn btn-primary"
                onClick={sendMessage}
                disabled={!input.trim() || thinking}
              >
                {thinking ? <span className="spinner" /> : <Send size={15} />}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
