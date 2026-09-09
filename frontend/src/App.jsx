import { useEffect, useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { API_BASE, apiGet } from './api/client'

export default function App() {
  // undefined = wird geladen, null = nicht eingeloggt, sonst {id, short_name, role, customer_id}
  const [user, setUser] = useState(undefined)

  useEffect(() => {
    apiGet('/api/auth/me')
      .then((data) => setUser(data.user))
      .catch(() => setUser(null))
  }, [])

  return (
    <>
      <nav
        className="flex flex-wrap items-center gap-4"
        style={{ padding: '1rem', background: '#241141', color: '#ffe9a8' }}
      >
        <strong>Stellenmarkt-AI (React PoC)</strong>
        <Link to="/" style={{ color: '#ffe9a8' }}>
          <i className="fa-solid fa-home" /> Start
        </Link>
        <Link to="/jobs" style={{ color: '#ffe9a8' }}>
          <i className="fa-solid fa-briefcase" /> Stellenangebote
        </Link>
        <Link to="/customers" style={{ color: '#ffe9a8' }}>
          <i className="fa-solid fa-building" /> Stellenanbieter
        </Link>
        {user?.role === 'admin' && (
          <Link to="/users" style={{ color: '#ffe9a8' }}>
            <i className="fa-solid fa-users" /> Nutzer
          </Link>
        )}
        <a href={API_BASE + '/'} style={{ color: '#ffe9a8', marginLeft: 'auto' }}>
          Zur klassischen Seite
        </a>
        <span>
          {user === undefined && 'Lade …'}
          {user === null && (
            <a href={API_BASE + '/login'} style={{ color: '#ffe9a8' }}>
              <i className="fa-solid fa-right-to-bracket" /> Anmelden
            </a>
          )}
          {user && (
            <>
              <i className="fa-solid fa-user" /> {user.short_name} ({user.role})
            </>
          )}
        </span>
      </nav>
      <main className="scroll full" style={{ padding: '1.5rem' }}>
        <Outlet context={{ user }} />
      </main>
    </>
  )
}
