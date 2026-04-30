import { useState, useEffect, useRef } from 'react'
import { Mic, Square, Loader, Play, Pause, RotateCcw, Trash2, Send } from 'lucide-react'
import { useAudioRecorder } from '../../hooks/useAudioRecorder'

export default function VoiceRecorder({
  onRecordingComplete,
  disabled = false,
  processing = false,
}) {
  const {
    isRecording,
    audioBlob,
    error,
    duration,
    startRecording,
    stopRecording,
    clearRecording,
  } = useAudioRecorder()

  // --- review state ---
  const [pendingBlob, setPendingBlob]       = useState(null)
  const [playbackUrl, setPlaybackUrl]       = useState(null)
  const [isPlayingBack, setIsPlayingBack]   = useState(false)
  const playbackRef = useRef(null)

  useEffect(() => {
    if (audioBlob && !isRecording) {
      if (playbackUrl) URL.revokeObjectURL(playbackUrl)
      const url = URL.createObjectURL(audioBlob)
      setPlaybackUrl(url)
      setPendingBlob(audioBlob)
      clearRecording()
    }
  }, [audioBlob, isRecording]) 

  // Clean up object URL on unmount
  useEffect(() => () => {
    if (playbackUrl) URL.revokeObjectURL(playbackUrl)
  }, [playbackUrl])

  const togglePlayback = () => {
    if (!playbackRef.current) return
    if (isPlayingBack) {
      playbackRef.current.pause()
    } else {
      playbackRef.current.currentTime = 0
      playbackRef.current.play().catch(() => {})
    }
  }

  const handleSend = () => {
    if (!pendingBlob) return
    onRecordingComplete(pendingBlob)
    setPendingBlob(null)
    setIsPlayingBack(false)
  }

  const handleReRecord = () => {
    setIsPlayingBack(false)
    setPendingBlob(null)
    if (playbackUrl) { URL.revokeObjectURL(playbackUrl); setPlaybackUrl(null) }
    startRecording()
  }

  const handleDelete = () => {
    setIsPlayingBack(false)
    setPendingBlob(null)
    if (playbackUrl) { URL.revokeObjectURL(playbackUrl); setPlaybackUrl(null) }
  }

  return (
    <div className="voice-input-row">
      {error && <div className="rec-error small red">{error}</div>}

      {playbackUrl && (
        <audio
          ref={playbackRef}
          src={playbackUrl}
          onPlay={() => setIsPlayingBack(true)}
          onPause={() => setIsPlayingBack(false)}
          onEnded={() => setIsPlayingBack(false)}
          style={{ display: 'none' }}
        />
      )}

      <div className="voice-controls">

        {/* ── Recording in progress ── */}
        {isRecording && (
          <>
            <div className="recording-indicator">
              <WaveformBars />
              <span className="rec-duration">{duration}s</span>
            </div>
            <button className="btn btn-danger" onClick={stopRecording}>
              <Square size={14} /> Stop
            </button>
          </>
        )}

        {/* ── API processing ── */}
        {!isRecording && processing && (
          <button className="btn btn-primary mic-btn" disabled>
            <Loader size={16} className="spinning" /> Processing…
          </button>
        )}

        {/* ── Review: confirm before sending ── */}
        {!isRecording && !processing && pendingBlob && (
          <div className="review-row">
            <button
              className="btn btn-ghost btn-sm"
              onClick={togglePlayback}
              title={isPlayingBack ? 'Pause' : 'Play your recording'}
            >
              {isPlayingBack ? <Pause size={13} /> : <Play size={13} />}
              Your recording
            </button>

            <div className="review-actions">
              <button
                className="btn btn-ghost btn-sm"
                onClick={handleReRecord}
                title="Record again"
              >
                <RotateCcw size={12} /> Re-record
              </button>
              <button
                className="btn btn-ghost btn-sm red-btn"
                onClick={handleDelete}
                title="Delete recording"
              >
                <Trash2 size={12} />
              </button>
              <button
                className="btn btn-primary btn-sm"
                onClick={handleSend}
              >
                <Send size={13} /> Send
              </button>
            </div>
          </div>
        )}

        {/* ── Idle: tap to speak ── */}
        {!isRecording && !processing && !pendingBlob && (
          <button
            className="btn btn-primary mic-btn"
            onClick={startRecording}
            disabled={disabled}
          >
            <Mic size={16} /> Tap to speak
          </button>
        )}

      </div>
    </div>
  )
}

function WaveformBars() {
  return (
    <div className="waveform" aria-hidden="true">
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} className="wave-bar" style={{ animationDelay: `${i * 0.12}s` }} />
      ))}
    </div>
  )
}
