import { Link, useNavigate } from 'react-router-dom'
import LoginForm from '../components/LoginForm'

export default function LoginPage() {
    const navigate = useNavigate()

    return (
        <div className="scroll">
            <h1 id="greetings">Anmelden</h1>
            <p className="subtitle">Melde dich mit deinen Zugangsdaten an</p>

            <LoginForm onLoggedIn={() => navigate('/')} />
            <p className="subtitle">
                Noch kein Konto? <Link to="/register">Jetzt registrieren</Link>
            </p>
        </div>
    )
}
