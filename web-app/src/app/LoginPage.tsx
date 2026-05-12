import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'
import { api } from '../lib/api'
import type { User } from '../lib/types'
import s from './LoginPage.module.css'

interface LoginResponse {
  access_token: string
  user: User
}

export function LoginPage() {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const login    = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await api.post<LoginResponse>('/api/v1/auth/login', { email, password })
      login(res.access_token, res.user)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar sesión.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={s.page}>
      <div className={s.card}>
        <div className={s.brand}>
          <svg className={s.brandMark} viewBox="0 0 500 500" aria-hidden="true">
            <g fill="none" stroke="currentColor" strokeWidth="34" strokeLinecap="round" strokeLinejoin="round">
              <path d="M 110 78 L 388 78" />
              <path d="M 388 78 L 110 430" />
              <path d="M 388 220 L 222 430" />
              <path d="M 388 362 L 334 430" />
            </g>
          </svg>
          <span className={s.brandName}>ZARIS</span>
        </div>

        <h1 className={s.title}>Iniciar sesión</h1>
        <p className={s.subtitle}>Gestión Estatal · Municipio Demo</p>

        <form className={s.form} onSubmit={handleSubmit} noValidate>
          <div className={s.field}>
            <label className={s.label} htmlFor="email">Correo electrónico</label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={s.input}
              placeholder="usuario@municipio.gob.ar"
              required
            />
          </div>

          <div className={s.field}>
            <label className={s.label} htmlFor="password">Contraseña</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={s.input}
              placeholder="••••••••"
              required
            />
          </div>

          <button type="submit" className={s.submit} disabled={loading}>
            {loading ? 'Ingresando…' : 'Ingresar'}
          </button>

          {error && <div className={s.error} role="alert">{error}</div>}
        </form>

        <p className={s.foot}>zaris-zge · v0.1</p>
      </div>
    </div>
  )
}
