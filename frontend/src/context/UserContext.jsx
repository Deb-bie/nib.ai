import { createContext, useContext, useState } from 'react'

const UserContext = createContext(null)

export function UserProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('tutor_user')) ?? null }
    catch { return null }
  })

  const [profile, setProfile] = useState(() => {
    try { return JSON.parse(localStorage.getItem('tutor_profile')) ?? null }
    catch { return null }
  })

  // All language profiles for this user
  const [allProfiles, setAllProfiles] = useState(() => {
    try { return JSON.parse(localStorage.getItem('tutor_all_profiles')) ?? [] }
    catch { return [] }
  })

  /**
   * Login — called after onboarding or sign-in.
   * @param {object}   userData   { username, email, user_id }
   * @param {object}   profileData  { profile_id, target_language, overall_level }
   * @param {object[]} profiles   All profiles for this user (optional)
   */
  const login = (userData, profileData, profiles = []) => {
    const profileList = profiles.length > 0 ? profiles : [profileData]
    setUser(userData)
    setProfile(profileData)
    setAllProfiles(profileList)
    localStorage.setItem('tutor_user', JSON.stringify(userData))
    localStorage.setItem('tutor_profile', JSON.stringify(profileData))
    localStorage.setItem('tutor_all_profiles', JSON.stringify(profileList))
  }

  const logout = () => {
    setUser(null)
    setProfile(null)
    setAllProfiles([])
    localStorage.removeItem('tutor_user')
    localStorage.removeItem('tutor_profile')
    localStorage.removeItem('tutor_all_profiles')
  }

  /** Update fields on the active profile (e.g. after assessment sets overall_level). */
  const updateProfile = (updates) => {
    const updated = { ...profile, ...updates }
    setProfile(updated)
    // Also sync into the allProfiles list
    setAllProfiles(prev => {
      const next = prev.map(p =>
        p.profile_id === updated.profile_id ? updated : p
      )
      localStorage.setItem('tutor_all_profiles', JSON.stringify(next))
      return next
    })
    localStorage.setItem('tutor_profile', JSON.stringify(updated))
  }

  /** Switch to a different language profile. */
  const switchProfile = (newProfile) => {
    setProfile(newProfile)
    localStorage.setItem('tutor_profile', JSON.stringify(newProfile))
  }

  /** Add a newly-created language profile and make it active. */
  const addProfile = (newProfile) => {
    setAllProfiles(prev => {
      const next = [...prev.filter(p => p.profile_id !== newProfile.profile_id), newProfile]
      localStorage.setItem('tutor_all_profiles', JSON.stringify(next))
      return next
    })
    setProfile(newProfile)
    localStorage.setItem('tutor_profile', JSON.stringify(newProfile))
  }

  return (
    <UserContext.Provider value={{
      user, profile, allProfiles,
      login, logout, updateProfile, switchProfile, addProfile,
    }}>
      {children}
    </UserContext.Provider>
  )
}

export const useUser = () => {
  const ctx = useContext(UserContext)
  if (!ctx) throw new Error('useUser must be used inside UserProvider')
  return ctx
}
