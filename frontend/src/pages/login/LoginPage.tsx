import { FormEvent, useState } from 'react'

import styles from './LoginPage.module.css'

const AUTH_NOT_CONNECTED_MESSAGE =
  'Авторизация пока не подключена к backend API.'

type FieldErrors = {
  username?: string
  password?: string
}

type FormStatus = {
  message: string
  tone: 'error' | 'info'
}

export function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [status, setStatus] = useState<FormStatus | null>(null)

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const nextErrors: FieldErrors = {}

    if (!username.trim()) {
      nextErrors.username = 'Введите email или логин.'
    }

    if (!password) {
      nextErrors.password = 'Введите пароль.'
    }

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      setStatus({
        message: 'Заполните обязательные поля.',
        tone: 'error',
      })
      return
    }

    setErrors({})
    setStatus({ message: AUTH_NOT_CONNECTED_MESSAGE, tone: 'info' })
  }

  return (
    <main className={styles.page}>
      <h1 className={styles.title}>Хроники Этельгарда</h1>

      <section className={styles.panel} aria-labelledby="login-heading">
        <div className={styles.panelOrnament} aria-hidden="true">
          ◆
        </div>
        <h2 id="login-heading" className={styles.panelTitle}>
          Врата приключений
        </h2>
        <p className={styles.intro}>
          Представьтесь, путник, чтобы продолжить свою историю.
        </p>

        <form className={styles.form} onSubmit={handleSubmit} noValidate>
          <div className={styles.field}>
            <label htmlFor="username">Email/Логин</label>
            <input
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              placeholder="Username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              aria-invalid={Boolean(errors.username)}
              aria-describedby={errors.username ? 'username-error' : undefined}
              required
            />
            {errors.username && (
              <span id="username-error" className={styles.fieldError}>
                {errors.username}
              </span>
            )}
          </div>

          <div className={styles.field}>
            <label htmlFor="password">Пароль</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              placeholder="Password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-invalid={Boolean(errors.password)}
              aria-describedby={errors.password ? 'password-error' : undefined}
              required
            />
            {errors.password && (
              <span id="password-error" className={styles.fieldError}>
                {errors.password}
              </span>
            )}
          </div>

          <button className={styles.loginButton} type="submit">
            <span>Войти</span>
          </button>

          <div
            className={styles.status}
            data-tone={status?.tone}
            role={status?.tone === 'error' ? 'alert' : 'status'}
            aria-live="polite"
          >
            {status?.message ?? '\u00a0'}
          </div>
        </form>
      </section>
    </main>
  )
}
