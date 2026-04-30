import { useState, useRef, useCallback } from 'react'

async function toWavBlob(inputBlob) {
  const arrayBuffer = await inputBlob.arrayBuffer()
  const tempCtx = new AudioContext()
  let decoded
  try {
    decoded = await tempCtx.decodeAudioData(arrayBuffer)
  } finally {
    tempCtx.close()
  }


  let monoBuffer = decoded
  if (decoded.numberOfChannels > 1) {
    const mono = new AudioBuffer({
      numberOfChannels: 1,
      length: decoded.length,
      sampleRate: decoded.sampleRate,
    })
    const dest = mono.getChannelData(0)
    for (let ch = 0; ch < decoded.numberOfChannels; ch++) {
      const src = decoded.getChannelData(ch)
      for (let i = 0; i < decoded.length; i++) {
        dest[i] += src[i] / decoded.numberOfChannels
      }
    }
    monoBuffer = mono
  }


  const TARGET_SR = 16_000
  const targetLength = Math.ceil(monoBuffer.duration * TARGET_SR)
  const offlineCtx = new OfflineAudioContext(1, targetLength, TARGET_SR)
  const source = offlineCtx.createBufferSource()
  source.buffer = monoBuffer
  source.connect(offlineCtx.destination)
  source.start(0)
  const resampled = await offlineCtx.startRendering()

  return _encodeWav(resampled.getChannelData(0), TARGET_SR)
}


function _encodeWav(samples, sampleRate) {
  const numSamples = samples.length
  const buf = new ArrayBuffer(44 + numSamples * 2)
  const view = new DataView(buf)

  function str(offset, s) {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i))
  }

  str(0,  'RIFF')
  view.setUint32( 4, 36 + numSamples * 2,  true)  // file size − 8
  str(8,  'WAVE')
  str(12, 'fmt ')
  view.setUint32(16, 16,              true)  
  view.setUint16(20,  1,              true)  
  view.setUint16(22,  1,              true)  
  view.setUint32(24, sampleRate,      true)  
  view.setUint32(28, sampleRate * 2,  true)  
  view.setUint16(32,  2,              true)  
  view.setUint16(34, 16,              true)  
  str(36, 'data')
  view.setUint32(40, numSamples * 2,  true)

  let offset = 44
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true)
    offset += 2
  }

  return new Blob([buf], { type: 'audio/wav' })
}


export function useAudioRecorder() {
  const [isRecording, setIsRecording]   = useState(false)
  const [audioBlob,   setAudioBlob]     = useState(null)
  const [error,       setError]         = useState(null)
  const [duration,    setDuration]      = useState(0)

  const mediaRecorderRef = useRef(null)
  const chunksRef        = useRef([])
  const streamRef        = useRef(null)
  const timerRef         = useRef(null)

  const startRecording = useCallback(async () => {
    setError(null)
    setAudioBlob(null)
    setDuration(0)
    chunksRef.current = []

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/ogg'

      const recorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const rawBlob = new Blob(chunksRef.current, { type: mimeType })
        try {
          // Convert → 16 kHz mono WAV so the backend needs no ffmpeg
          const wavBlob = await toWavBlob(rawBlob)
          setAudioBlob(wavBlob)
        } catch (convErr) {
          console.warn('WAV conversion failed, sending raw audio:', convErr)
          setAudioBlob(rawBlob)   // fallback — requires ffmpeg on server
        }
      }

      recorder.start(100)
      setIsRecording(true)
      timerRef.current = setInterval(() => setDuration(d => d + 1), 1000)

    } catch (err) {
      setError(
        err.name === 'NotAllowedError'
          ? 'Microphone access denied. Please allow microphone access in your browser.'
          : `Could not start recording: ${err.message}`
      )
    }
  }, [])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
      clearInterval(timerRef.current)
    }
  }, [isRecording])

  const clearRecording = useCallback(() => {
    setAudioBlob(null)
    setDuration(0)
    setError(null)
  }, [])

  return { isRecording, audioBlob, error, duration, startRecording, stopRecording, clearRecording }
}
