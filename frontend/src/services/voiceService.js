import api from './api'

const voiceService = {
  transcribe: async (audioBlob, languageKey) => {
    const form = new FormData()
    // Blob is already 16 kHz WAV (converted by useAudioRecorder)
    form.append('audio', audioBlob, 'recording.wav')
    form.append('language_key', languageKey)
    return api
      .post('/voice/transcribe', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60_000,
      })
      .then(r => r.data)
  },

  speak: async (text, languageKey, slow = false) => {
    const res = await api.post(
      '/voice/speak',
      { text, language_key: languageKey, slow },
      { responseType: 'blob', timeout: 30_000 },
    )
    return URL.createObjectURL(res.data)
  },

  speakWord: async (word, languageKey) => {
    const res = await api.post(
      '/voice/speak/word',
      { word, language_key: languageKey },
      { responseType: 'blob', timeout: 30_000 },
    )
    return URL.createObjectURL(res.data)
  },


  sessionMessage: async (audioBlob, profileId, languageKey, learnerLevel = '', expectedText = '') => {
    const form = new FormData()
    form.append('audio', audioBlob, 'recording.wav')
    form.append('profile_id', profileId)
    form.append('language_key', languageKey)
    form.append('learner_level', learnerLevel)
    form.append('expected_text', expectedText)
    return api
      .post('/voice/session-message', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 90_000, 
      })
      .then(r => r.data)
  },


  checkPronunciation: async (expectedText, transcript, confidence, words, languageKey) => {
    return api
      .post('/voice/check-pronunciation', {
        expected_text: expectedText,
        transcript,
        confidence,
        words: words || [],
        language_key: languageKey,
      })
      .then(r => r.data)
  },
}

export default voiceService
