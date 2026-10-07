import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { API_BASE, apiGet, apiPost } from './api/client'
import { ConfirmProvider } from './components/ConfirmProvider'

export default function App() {
    // undefined = wird geladen, null = nicht eingeloggt, sonst {id, short_name, role, customer_id}
    const [user, setUser] = useState(undefined)
    // Hamburger-Menü unterhalb des md-Breakpoints, analog zu #nav-toggle/#nav-links
    // in templates/navigation.html - dort per Vanilla-JS/hidden-Klasse gelöst, hier
    // per State, da React die Navigation clientseitig rendert.
    const [navOpen, setNavOpen] = useState(false)
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
        <ConfirmProvider>
            <nav
                className="app-nav flex flex-wrap items-center"
                style={{ position: 'relative', zIndex: 2 }}
            >
                <i className="fa-solid fa-frog text-2xl text-[#76A250]"></i>
                <img
                    src={`${API_BASE}/static/pics/umweltmarkt_logo.png`}
                    alt="Stellenmarkt-Umweltschutz.de"
                    style={{ height: '2.25rem', marginRight: '1rem', marginLeft: '-0.25rem' }}
                />
                <button
                    type="button"
                    className="md:hidden nav-toggle"
                    aria-label="Menü öffnen"
                    aria-expanded={navOpen}
                    aria-controls="nav-links"
                    onClick={() => setNavOpen((open) => !open)}
                >
                    <i className="fa-solid fa-bars" />
                </button>
                <div
                    id="nav-links"
                    className={`${navOpen ? 'flex' : 'hidden'} md:flex w-full md:flex-1 flex-col md:flex-row md:items-center gap-1 mt-3 md:mt-0`}
                >
                    <strong
                        style={{
                            fontFamily: 'var(--heading-font)',
                            fontWeight: 'var(--heading-weight)',
                        }}
                    >
                        {/*Stellenmarkt-AI*/}
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
                    {user === undefined && (
                        <span style={{ marginLeft: 'auto' }}>Lade …</span>
                    )}
                    {user !== undefined && (
                        <details
                            ref={accountMenuRef}
                            className="nav-account"
                            style={{ position: 'relative', marginLeft: 'auto' }}
                        >
                            <summary>
                                <i className="fa-solid fa-user text-[#76A250]" />{' '}
                                {user ? user.short_name : 'Konto'}
                                <i
                                    className="fa-solid fa-chevron-down"
                                    style={{ fontSize: '0.7em' }}
                                />
                            </summary>
                            <div
                                className="nav-dropdown"
                                style={{ right: 0 }}
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
                                                onClick={() => {
                                                    if (accountMenuRef.current)
                                                        accountMenuRef.current.open = false
                                                }}
                                            >
                                                <i className="fa-solid fa-file-lines text-[#76A250]" />{' '}
                                                Lebenslauf
                                            </Link>
                                        )}
                                        {/* Tools (nur Testdaten-Generierung) bewusst im
                                            Konto-Menü statt als eigener Reiter - sie
                                            gehören nicht zum eigentlichen Produkt. */}
                                        {user.role === 'admin' && (
                                            <>
                                                <Link
                                                    to="/tools/resume"
                                                    className={navClass(
                                                        location.pathname ===
                                                            '/tools/resume',
                                                    )}
                                                    onClick={() => {
                                                        if (accountMenuRef.current)
                                                            accountMenuRef.current.open = false
                                                    }}
                                                >
                                                    <i className="fa-solid fa-file-lines text-[#76A250]" />{' '}
                                                    Lebenslauf generieren
                                                </Link>
                                                <Link
                                                    to="/tools/joboffer"
                                                    className={navClass(
                                                        location.pathname ===
                                                            '/tools/joboffer',
                                                    )}
                                                    onClick={() => {
                                                        if (accountMenuRef.current)
                                                            accountMenuRef.current.open = false
                                                    }}
                                                >
                                                    <i className="fa-solid fa-briefcase text-[#76A250]" />{' '}
                                                    Stellenangebot generieren
                                                </Link>
                                                <hr className="nav-dropdown-divider" />
                                            </>
                                        )}
                                        <Link
                                            to="/profile"
                                            className={navClass(
                                                location.pathname === '/profile',
                                            )}
                                            onClick={() => {
                                                if (accountMenuRef.current)
                                                    accountMenuRef.current.open = false
                                            }}
                                        >
                                            <i className="fa-solid fa-user-pen text-[#76A250]" />{' '}
                                            Einstellungen
                                        </Link>
                                        <button
                                            type="button"
                                            className="nav-menu-item"
                                            onClick={handleLogout}
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
            <main className="app-main">
                <Outlet context={{ user, refreshUser }} />
            </main>
        </ConfirmProvider>
    )
}
