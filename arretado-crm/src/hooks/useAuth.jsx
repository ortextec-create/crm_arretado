import { createContext, useContext, useState, useCallback } from 'react'
import { authApi } from '../api/services'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => authApi.me())

  const login = useCallback(async (email, password) => {
    const u = await authApi.login(email, password)
    setUser(u)
    return u
  }, [])

  const logout = useCallback(() => {
    authApi.logout()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuth: !!user }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
