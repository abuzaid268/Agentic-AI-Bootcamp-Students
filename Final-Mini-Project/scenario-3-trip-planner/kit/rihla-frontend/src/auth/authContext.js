import { createContext, useContext } from 'react'

export const AuthContext = createContext(null)

// { user, status: 'loading' | 'signed_in' | 'signed_out', requireAuth, openLogin, closeLogin, signInWithGoogle,
//   logout, sessionExpired } — see AuthProvider.jsx.
export function useAuth() {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error('useAuth() must be used inside <AuthProvider>.')
  return auth
}
