
import { useState, useEffect, useRef } from 'react'
import { Play, Pause, Volume2 } from 'lucide-react'

export default function AudioPlayer({
  audioB64,
  audioUrl,
  contentType = 'audio/mpeg',
  autoPlay = true,
  label = 'Play reply',
}) {
  const audioRef  = useRef(null)
  const [url, setUrl]               = useState(null)
  const [playing, setPlaying]       = useState(false)
  const [current, setCurrent]       = useState(0)
  const [duration, setDuration]     = useState(0) 

  // Build object URL from base64 or use the provided URL
  useEffect(() => {
    if (audioB64) {
      try {
        const bytes = Uint8Array.from(atob(audioB64), c => c.charCodeAt(0))
        const blob  = new Blob([bytes], { type: contentType })
        const obj   = URL.createObjectURL(blob)
        setUrl(obj)
        return () => URL.revokeObjectURL(obj)
      } catch { /* ignore malformed base64 */ }
    } else if (audioUrl) {
      setUrl(audioUrl)
    } else {
      setUrl(null)
    }
  }, [audioB64, audioUrl, contentType])

  // Auto-play when a new URL arrives
  useEffect(() => {
    if (url && autoPlay && audioRef.current) {
      audioRef.current.play().catch(() => {})
    }
  }, [url, autoPlay])

  const toggle = () => {
    if (!audioRef.current) return
    playing ? audioRef.current.pause() : audioRef.current.play().catch(() => {})
  }

  const handleSeek = (e) => {
    if (!audioRef.current || !duration) return
    const pct = Number(e.target.value) / 100
    audioRef.current.currentTime = pct * duration
    setCurrent(pct * duration)
  }

  const fmt = (s) => {
    if (!s || !isFinite(s)) return '0:00'
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  if (!url) return null

  const pct = duration ? (current / duration) * 100 : 0

  return (
    <div className="audio-player">
      <audio
        ref={audioRef}
        src={url}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => { setPlaying(false); setCurrent(0) }}
        onTimeUpdate={() => setCurrent(audioRef.current?.currentTime ?? 0)}
        onLoadedMetadata={() => setDuration(audioRef.current?.duration ?? 0)}
      />

      <div className="audio-controls">
        <button
          className="audio-play-btn btn btn-ghost"
          onClick={toggle}
          title={playing ? 'Pause' : 'Play'}
          aria-label={playing ? 'Pause' : 'Play'}
        >
          <Volume2 size={13} />
          {playing ? <Pause size={12} /> : <Play size={12} />}
          <span className="small">{label}</span>
        </button>

        <div className="audio-seek">
          <span className="audio-time small muted">{fmt(current)}</span>
          <input
            type="range"
            className="audio-seek-bar"
            min={0}
            max={100}
            step={0.5}
            value={pct}
            onChange={handleSeek}
            aria-label="Seek"
          />
          <span className="audio-time small muted">{fmt(duration)}</span>
        </div>
      </div>
    </div>
  )
}
