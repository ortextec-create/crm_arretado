import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { authApi, usuariosApi } from '../api/services'
import { aplicarTema } from '../utils/tema'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => authApi.me())

  // Fase 3 (temas, ver MULTIEMPRESA.md) — reage a login/logout/troca de
  // empresa/troca de preferência de tema, sempre a partir do mesmo `user`
  // já cacheado (nenhuma chamada de API extra aqui).
  useEffect(() => {
    aplicarTema({ empresa: user?.empresa_ativa || null, preferenciaTema: user?.preferencia_tema })
    document.title = `${user?.empresa_ativa?.nome || 'Arretado Doces'} — CRM`
    const favicon = document.querySelector('link[rel="icon"]')
    if (favicon && user?.empresa_ativa?.logo_simbolo) {
      favicon.href = user.empresa_ativa.logo_simbolo
    }
  }, [user])

  const login = useCallback(async (email, password) => {
    const u = await authApi.login(email, password)
    setUser(u)
    return u
  }, [])

  const logout = useCallback(async () => {
    await authApi.logout()
    setUser(null)
  }, [])

  // Multi-Empresa — Fase 2 (ver MULTIEMPRESA.md). Troca sempre passa pelo
  // backend primeiro (fonte da verdade de Usuario.empresa_ativa) — só depois
  // atualiza o estado local e o espelho em localStorage.
  const trocarEmpresa = useCallback(async (empresaId) => {
    const res = await usuariosApi.definirEmpresaAtiva(empresaId)
    const atualizado = authApi.atualizarCache({ empresa_ativa: res.data.empresa_ativa })
    setUser(atualizado)
    return atualizado
  }, [])

  const definirPreferenciaTema = useCallback(async (tema) => {
    const res = await usuariosApi.preferenciaTema(tema)
    const atualizado = authApi.atualizarCache({ preferencia_tema: res.data.preferencia_tema })
    setUser(atualizado)
    return atualizado
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        logout,
        isAuth: !!user,
        empresas: user?.empresas || [],
        empresaAtiva: user?.empresa_ativa || null,
        trocarEmpresa,
        definirPreferenciaTema,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
