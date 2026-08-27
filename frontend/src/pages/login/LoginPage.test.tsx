import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LoginPage } from './LoginPage'

function fillForm() {
  fireEvent.change(screen.getByLabelText(/email\/логин/i), {
    target: { value: 'traveler@example.com' },
  })
  fireEvent.change(screen.getByLabelText(/пароль/i), {
    target: { value: 'a-secret-kept-in-the-browser' },
  })
}

describe('LoginPage', () => {
  it('renders the login page', () => {
    render(<LoginPage />)

    expect(
      screen.getByRole('heading', { name: 'Хроники Этельгарда' }),
    ).toBeInTheDocument()
  })

  it('renders the username input', () => {
    render(<LoginPage />)

    expect(screen.getByLabelText(/email\/логин/i)).toHaveAttribute(
      'autocomplete',
      'username',
    )
  })

  it('renders the password input', () => {
    render(<LoginPage />)

    expect(screen.getByLabelText(/пароль/i)).toHaveAttribute(
      'type',
      'password',
    )
  })

  it('renders the login button', () => {
    render(<LoginPage />)

    expect(screen.getByRole('button', { name: 'Войти' })).toBeInTheDocument()
  })

  it('shows validation when empty values are submitted', () => {
    render(<LoginPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))

    expect(screen.getByText('Введите email или логин.')).toBeInTheDocument()
    expect(screen.getByText('Введите пароль.')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Заполните обязательные поля.',
    )
  })

  it('submits valid presentation-only values', () => {
    render(<LoginPage />)
    fillForm()

    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))

    expect(screen.getByRole('status')).toHaveTextContent(
      'Авторизация пока не подключена к backend API.',
    )
  })

  it('does not fake a successful authentication', () => {
    render(<LoginPage />)
    fillForm()

    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))

    expect(screen.queryByText(/успешн/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/добро пожаловать/i)).not.toBeInTheDocument()
    expect(screen.getByLabelText(/email\/логин/i)).toHaveValue(
      'traveler@example.com',
    )
    expect(screen.getByLabelText(/пароль/i)).toHaveValue(
      'a-secret-kept-in-the-browser',
    )
  })
})
