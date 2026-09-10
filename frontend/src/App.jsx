import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { API_BASE, apiGet, apiPost } from './api/client'

export default function App() {
    // undefined = wird geladen, null = nicht eingeloggt, sonst {id, short_name, role, customer_id}
    const [user, setUser] = useState(undefined)
    // Hamburger-Menü unterhalb des md-Breakpoints, analog zu #nav-toggle/#nav-links
    // in templates/navigation.html - dort per Vanilla-JS/hidden-Klasse gelöst, hier
    // per State, da React die Navigation clientseitig rendert.
    const [navOpen, setNavOpen] = useState(false)
    const toolsMenuRef = useRef(null)
    const accountMenuRef = useRef(null)
    const location = useLocation()
    const navigate = useNavigate()

    const refreshUser = useCallback(() => {
        return apiGet('/api/auth/me')
            .then((data) => setUser(data.user))
            .catch(() => setUser(null))
    }, [])

    useEffect(() => {
        refreshUser()
    }, [refreshUser])

    // Klassisch löst das durch volle Seitenreloads bei jeder Navigation implizit -
    // hier stattdessen explizit schließen, sonst bliebe das aufgeklappte
    // Hamburger-Menü nach einem Klick auf einen Link (SPA-Navigation ohne Reload)
    // stehen.
    useEffect(() => {
        setNavOpen(false)
    }, [location.pathname])

    function navClass(active) {
        return active ? 'active' : undefined
    }

    async function handleLogout() {
        if (accountMenuRef.current) accountMenuRef.current.open = false
        await apiPost('/api/auth/logout', {})
        await refreshUser()
        navigate('/')
    }

    return (
        <>
            <nav
                className="flex flex-wrap items-center"
                style={{ padding: '1rem', position: 'relative', zIndex: 2 }}
            >
                <button
                    type="button"
                    className="md:hidden"
                    aria-label="Menü öffnen"
                    aria-expanded={navOpen}
                    aria-controls="nav-links"
                    onClick={() => setNavOpen((open) => !open)}
                    style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--gold-2)',
                        fontSize: '1.1rem',
                        padding: '0.2rem',
                        cursor: 'pointer',
                    }}
                >
                    <i className="fa-solid fa-bars" />
                </button>
                <div
                    id="nav-links"
                    className={`${navOpen ? 'flex' : 'hidden'} md:flex w-full md:flex-1 flex-col md:flex-row md:items-center gap-4 mt-3 md:mt-0`}
                >
                    <strong
                        style={{
                            fontFamily: 'var(--heading-font)',
                            fontWeight: 'var(--heading-weight)',
                        }}
                    >
                        Stellenmarkt-AI (React)
                    </strong>
                    <Link
                        to="/"
                        className={navClass(location.pathname === '/')}
                    >
                        <i className="fa-solid fa-home text-[#76A250]" /> Start
                    </Link>
                    <Link
                        to="/jobs"
                        className={navClass(
                            location.pathname.startsWith('/jobs'),
                        )}
                    >
                        <i className="fa-solid fa-briefcase text-[#76A250]" />{' '}
                        Stellenangebote
                    </Link>
                    <Link
                        to="/customers"
                        className={navClass(
                            location.pathname.startsWith('/customers'),
                        )}
                    >
                        <i className="fa-solid fa-building text-[#76A250]" />{' '}
                        Stellenanbieter
                    </Link>
                    {user?.role === 'admin' && (
                        <Link
                            to="/users"
                            className={navClass(
                                location.pathname.startsWith('/users'),
                            )}
                        >
                            <i className="fa-solid fa-users text-[#76A250]" />{' '}
                            Nutzer
                        </Link>
                    )}
                    {user?.role === 'admin' && (
                        <details
                            ref={toolsMenuRef}
                            style={{ position: 'relative' }}
                        >
                            <summary
                                style={{
                                    cursor: 'pointer',
                                    listStyle: 'none',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.4rem',
                                    color: 'var(--gold-2)',
                                }}
                            >
                                <i className="fa-solid fa-toolbox text-[#76A250]" />{' '}
                                Tools
                                <i
                                    className="fa-solid fa-chevron-down"
                                    style={{ fontSize: '0.7em' }}
                                />
                            </summary>
                            <div
                                style={{
                                    position: 'absolute',
                                    left: 0,
                                    marginTop: '0.5rem',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    minWidth: '13rem',
                                    background: 'var(--field-bg)',
                                    border: '1px solid var(--card-border)',
                                    borderRadius: 'var(--radius-ctl)',
                                    overflow: 'hidden',
                                    zIndex: 10,
                                }}
                            >
                                <Link
                                    to="/tools/resume"
                                    className={navClass(
                                        location.pathname === '/tools/resume',
                                    )}
                                    style={{ padding: '0.5rem 1rem' }}
                                    onClick={() => {
                                        if (toolsMenuRef.current)
                                            toolsMenuRef.current.open = false
                                    }}
                                >
                                    <i className="fa-solid fa-file-lines text-[#76A250]" />{' '}
                                    Lebenslauf generieren
                                </Link>
                                <Link
                                    to="/tools/joboffer"
                                    className={navClass(
                                        location.pathname === '/tools/joboffer',
                                    )}
                                    style={{ padding: '0.5rem 1rem' }}
                                    onClick={() => {
                                        if (toolsMenuRef.current)
                                            toolsMenuRef.current.open = false
                                    }}
                                >
                                    <i className="fa-solid fa-file-lines text-[#76A250]" />{' '}
                                    Stellenangebot generieren
                                </Link>
                            </div>
                        </details>
                    )}
                    <a
                        href={API_BASE + '/?classic=1'}
                        style={{ marginLeft: 'auto' }}
                    >
                        <i className="fa-solid fa-landmark text-[#76A250]" />{' '}
                        Klassisch
                    </a>
                    {user === undefined && <span>Lade …</span>}
                    {user !== undefined && (
                        <details
                            ref={accountMenuRef}
                            style={{ position: 'relative' }}
                        >
                            <summary
                                style={{
                                    cursor: 'pointer',
                                    listStyle: 'none',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.4rem',
                                    color: 'var(--gold-2)',
                                }}
                            >
                                <i className="fa-solid fa-user text-[#76A250]" />{' '}
                                {user ? user.short_name : 'Konto'}
                                <i
                                    className="fa-solid fa-chevron-down"
                                    style={{ fontSize: '0.7em' }}
                                />
                            </summary>
                            <div
                                style={{
                                    position: 'absolute',
                                    right: 0,
                                    marginTop: '0.5rem',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    minWidth: '12rem',
                                    background: 'var(--field-bg)',
                                    border: '1px solid var(--card-border)',
                                    borderRadius: 'var(--radius-ctl)',
                                    overflow: 'hidden',
                                    zIndex: 10,
                                }}
                            >
                                {user ? (
                                    <>
                                        {user.role === 'user' && (
                                            <Link
                                                to="/resumes"
                                                className={navClass(
                                                    location.pathname ===
                                                        '/resumes',
                                                )}
                                                style={{
                                                    padding: '0.5rem 1rem',
                                                }}
                                            >
                                                <i className="fa-solid fa-file-lines text-[#76A250]" />{' '}
                                                Lebenslauf
                                            </Link>
                                        )}
                                        <button
                                            type="button"
                                            onClick={handleLogout}
                                            style={{
                                                padding: '0.5rem 1rem',
                                                background: 'none',
                                                border: 'none',
                                                color: 'var(--gold-2)',
                                                font: 'inherit',
                                                fontSize: '0.78rem',
                                                textTransform: 'uppercase',
                                                letterSpacing: '0.4px',
                                                textAlign: 'left',
                                                cursor: 'pointer',
                                            }}
                                        >
                                            <i className="fa-solid fa-right-from-bracket text-[#76A250]" />{' '}
                                            Abmelden
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        <Link
                                            to="/login"
                                            className={navClass(
                                                location.pathname === '/login',
                                            )}
                                            style={{ padding: '0.5rem 1rem' }}
                                            onClick={() => {
                                                if (accountMenuRef.current)
                                                    accountMenuRef.current.open = false
                                            }}
                                        >
                                            <i className="fa-solid fa-right-to-bracket text-[#76A250]" />{' '}
                                            Anmelden
                                        </Link>
                                        <Link
                                            to="/register"
                                            className={navClass(
                                                location.pathname ===
                                                    '/register',
                                            )}
                                            style={{ padding: '0.5rem 1rem' }}
                                            onClick={() => {
                                                if (accountMenuRef.current)
                                                    accountMenuRef.current.open = false
                                            }}
                                        >
                                            <i className="fa-solid fa-user-plus text-[#76A250]" />{' '}
                                            Registrieren
                                        </Link>
                                    </>
                                )}
                            </div>
                        </details>
                    )}
                </div>
            </nav>
            <main className="scroll full" style={{ padding: '1.5rem' }}>
                <Outlet context={{ user, refreshUser }} />
            </main>
        </>
    )
}
