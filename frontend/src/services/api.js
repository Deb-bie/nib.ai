import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000,
})

// ── Profile / Onboarding ──────────────────────────────────────────────────────

export const profileService = {
  create: (data) => api.post('/profile/create', data).then(r => r.data),
  get: (profileId) => api.get(`/profile/${profileId}`).then(r => r.data),
  dashboard: (profileId) => api.get(`/profile/${profileId}/dashboard`).then(r => r.data),
  languages: () => api.get('/profile/languages/supported').then(r => r.data),
  startAssessment: (profileId) =>
    api.post('/profile/assessment/start', null, { params: { profile_id: profileId } }).then(r => r.data),
  sendAssessmentMessage: (profileId, message) =>
    api.post('/profile/assessment/message', { profile_id: profileId, message }).then(r => r.data),
  // Add a new target language for an existing user account
  addLanguage: (data) => api.post('/profile/add-language', data).then(r => r.data),
}

// ── Session ───────────────────────────────────────────────────────────────────

export const sessionService = {
  start: (profileId, inputMode = 'text') =>
    api.post('/session/start', { profile_id: profileId, input_mode: inputMode }).then(r => r.data),
  message: (profileId, message) =>
    api.post('/session/message', { profile_id: profileId, message }).then(r => r.data),
  end: (profileId) =>
    api.post('/session/end', { profile_id: profileId }).then(r => r.data),
  status: (profileId) =>
    api.get(`/session/status/${profileId}`).then(r => r.data),
}

// ── Voice ─────────────────────────────────────────────────────────────────────

export const voiceService = {
  transcribe: async (audioBlob, languageKey) => {
    const form = new FormData()
    form.append('audio', audioBlob, 'recording.wav')
    form.append('language_key', languageKey)
    return api.post('/voice/transcribe', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },

  // learnerLevel controls slow-mode: A1/A2/unassessed → slow, B1+ → normal speed
  speak: async (text, languageKey, learnerLevel = '') => {
    const res = await api.post('/voice/speak', {
      text,
      language_key: languageKey,
      learner_level: learnerLevel,
    }, { responseType: 'blob', timeout: 90000 })
    return URL.createObjectURL(res.data)
  },

  speakWord: async (word, languageKey) => {
    const res = await api.post('/voice/speak/word', { word, language_key: languageKey }, {
      responseType: 'blob',
    })
    return URL.createObjectURL(res.data)
  },

  sessionMessage: async (audioBlob, profileId, languageKey, learnerLevel = '', expectedText = '') => {
    const form = new FormData()
    form.append('audio', audioBlob, 'recording.wav')
    form.append('profile_id', profileId)
    form.append('language_key', languageKey)
    form.append('learner_level', learnerLevel)
    form.append('expected_text', expectedText)
    return api.post('/voice/session-message', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 90000,
    }).then(r => r.data)
  },
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authService = {
  register: (data) => api.post('/auth/register', data).then(r => r.data),
  login: (email, password) =>
    api.post('/auth/login', { email, password }).then(r => r.data),
  loginByUsername: (username) =>
    api.post('/auth/login/username', { username }).then(r => r.data),
}

// ── Session History ───────────────────────────────────────────────────────────

export const sessionHistoryService = {
  all: (profileId) =>
    api.get(`/session/history/${profileId}`).then(r => r.data),
  messages: (sessionId) =>
    api.get(`/session/${sessionId}/messages`).then(r => r.data),
}

// ── Progress ──────────────────────────────────────────────────────────────────

export const progressService = {
  errors: (profileId) => api.get(`/progress/${profileId}/errors`).then(r => r.data),
  skills: (profileId) => api.get(`/progress/${profileId}/skills`).then(r => r.data),
  vocabulary: (profileId) => api.get(`/progress/${profileId}/vocabulary`).then(r => r.data),
  plan: (profileId) => api.get(`/progress/${profileId}/plan`).then(r => r.data),
}

export default api
