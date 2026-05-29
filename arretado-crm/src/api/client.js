import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Injeta token em todas as requisições
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) config.headers.Authorization = `Token ${token}`
  return config
})

// Interceptor de resposta:
// Redireciona para /login em 401, MAS ignora a rota de login
// para não causar redirect durante a tentativa de autenticação.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const isLoginEndpoint = err.config?.url?.includes('/usuarios/login/')
    if (err.response?.status === 401 && !isLoginEndpoint) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api