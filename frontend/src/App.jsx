import { useEffect, useRef, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { API_BASE, apiGet } from './api/client'

export default function App() {
  // undefined = wird geladen, null = nicht eingeloggt, sonst {id, short_name, role, customer_id}
  const [user, setUser] = useState(undefined)
  const toolsMenuRef = useRef(null)
  const location = useLocation()

  useEffect(() => {
    apiGet('/api/auth/me')
      .then((data) => setUser(data.user))
      .catch(() => setUser(null))
  }, [])

  function navClass(active) {
    return active ? 'active' : undefined
  }

  return (
    <>
      <nav
        className="flex flex-wrap items-center gap-4"
        style={{ padding: '1rem', background: '#241141', color: '#ffe9a8', position: 'relative', zIndex: 2 }}
      >
        <strong>Stellenmarkt-AI (React)</strong>
        <Link to="/" className={navClass(location.pathname === '/')}>
          <i className="fa-solid fa-home text-[#76A250]" /> Start
        </Link>
        <Link to="/jobs" className={navClass(location.pathname.startsWith('/jobs'))}>
          <i className="fa-solid fa-briefcase text-[#76A250]" /> Stellenangebote
        </Link>
        <Link to="/customers" className={navClass(location.pathname.startsWith('/customers'))}>
          <i className="fa-solid fa-building text-[#76A250]" /> Stellenanbieter
        </Link>
        {user?.role === 'admin' && (
          <Link to="/users" className={navClass(location.pathname.startsWith('/users'))}>
            <i className="fa-solid fa-users text-[#76A250]" /> Nutzer
          </Link>
        )}
        {user?.role === 'admin' && (
          <details ref={toolsMenuRef} style={{ position: 'relative' }}>
            <summary
              style={{
                cursor: 'pointer',
                listStyle: 'none',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                color: '#ffe9a8',
              }}
            >
              <i className="fa-solid fa-toolbox text-[#76A250]" /> Tools
              <i className="fa-solid fa-chevron-down" style={{ fontSize: '0.7em' }} />
            </summary>
            <div
              style={{
                position: 'absolute',
                left: 0,
                marginTop: '0.5rem',
                display: 'flex',
                flexDirection: 'column',
                minWidth: '13rem',
                background: '#241141',
                border: '1px solid rgba(255, 215, 130, 0.35)',
                borderRadius: '8px',
                overflow: 'hidden',
                zIndex: 10,
              }}
            >
              <Link
                to="/tools/resume"
                className={navClass(location.pathname === '/tools/resume')}
                style={{ padding: '0.5rem 1rem' }}
                onClick={() => {
                  if (toolsMenuRef.current) toolsMenuRef.current.open = false
                }}
              >
                <i className="fa-solid fa-file-lines text-[#76A250]" /> Lebenslauf generieren
              </Link>
              <Link
                to="/tools/joboffer"
                className={navClass(location.pathname === '/tools/joboffer')}
                style={{ padding: '0.5rem 1rem' }}
                onClick={() => {
                  if (toolsMenuRef.current) toolsMenuRef.current.open = false
                }}
              >
                <i className="fa-solid fa-file-lines text-[#76A250]" /> Stellenangebot generieren
              </Link>
            </div>
          </details>
        )}
        <a href={API_BASE + '/'} style={{ marginLeft: 'auto' }}>
          <i className="fa-solid fa-landmark text-[#76A250]" /> Klassisch
        </a>
        {user === undefined && <span>Lade …</span>}
        {user !== undefined && (
          <details style={{ position: 'relative' }}>
            <summary
              style={{
                cursor: 'pointer',
                listStyle: 'none',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                color: '#ffe9a8',
              }}
            >
              <i className="fa-solid fa-user text-[#76A250]" /> {user ? user.short_name : 'Konto'}
              <i className="fa-solid fa-chevron-down" style={{ fontSize: '0.7em' }} />
            </summary>
            <div
              style={{
                position: 'absolute',
                right: 0,
                marginTop: '0.5rem',
                display: 'flex',
                flexDirection: 'column',
                minWidth: '12rem',
                background: '#241141',
                border: '1px solid rgba(255, 215, 130, 0.35)',
                borderRadius: '8px',
                overflow: 'hidden',
                zIndex: 10,
              }}
            >
              {user ? (
                <>
                  {user.role === 'user' && (
                    <Link to="/resumes" className={navClass(location.pathname === '/resumes')} style={{ padding: '0.5rem 1rem' }}>
                      <i className="fa-solid fa-file-lines text-[#76A250]" /> Lebenslauf
                    </Link>
                  )}
                  <a href={API_BASE + '/logout'} style={{ padding: '0.5rem 1rem' }}>
                    <i className="fa-solid fa-right-from-bracket text-[#76A250]" /> Abmelden
                  </a>
                </>
              ) : (
                <>
                  <a href={API_BASE + '/login'} style={{ padding: '0.5rem 1rem' }}>
                    <i className="fa-solid fa-right-to-bracket text-[#76A250]" /> Anmelden
                  </a>
                  <a href={API_BASE + '/register'} style={{ padding: '0.5rem 1rem' }}>
                    <i className="fa-solid fa-user-plus text-[#76A250]" /> Registrieren
                  </a>
                </>
              )}
            </div>
          </details>
        )}
      </nav>
      <main className="scroll full" style={{ padding: '1.5rem' }}>
        <Outlet context={{ user }} />
      </main>
    </>
  )
}
