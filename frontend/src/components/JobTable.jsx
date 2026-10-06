import { Link } from 'react-router-dom'

// Ab so vielen Tagen Restlaufzeit gilt eine Stelle als "läuft bald ab".
const EXPIRING_DAYS = 14

// ISO-Datum (YYYY-MM-DD) als lokales Datum ohne Uhrzeit - new Date('YYYY-MM-DD')
// würde als UTC interpretiert und könnte je nach Zeitzone einen Tag verrutschen.
function parseIsoDate(iso) {
    if (!iso) return null
    const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
    return new Date(y, m - 1, d)
}

export function formatDate(iso) {
    const date = parseIsoDate(iso)
    return date ? date.toLocaleDateString('de-DE') : '-'
}

export function jobStatus(job) {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const from = parseIsoDate(job.valid_from)
    const until = parseIsoDate(job.valid_until)
    if (from && from > today) return { key: 'planned', label: 'Geplant' }
    if (until && until < today) return { key: 'expired', label: 'Abgelaufen' }
    if (until && (until - today) / 86400000 <= EXPIRING_DAYS)
        return { key: 'expiring', label: 'Läuft bald ab' }
    return { key: 'active', label: 'Aktiv' }
}

export default function JobTable({
    jobs,
    isAdmin,
    isCustomerUser,
    currentCustomerId,
    onDelete,
}) {
    return (
        <div style={{ overflowX: 'auto', marginBottom: '16px' }}>
            <table className="user-table" style={{ marginBottom: 0 }}>
                <thead>
                    <tr>
                        <th>Position</th>
                        <th>Stellenanbieter</th>
                        <th>Ort</th>
                        <th>Gültig bis</th>
                        <th>Status</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    {jobs.length === 0 && (
                        <tr>
                            <td colSpan={6}>Noch keine Stelle angelegt.</td>
                        </tr>
                    )}
                    {jobs.map((job) => {
                        const rowCanManage =
                            isAdmin ||
                            (isCustomerUser &&
                                job.customer_id === currentCustomerId)
                        const status = jobStatus(job)
                        return (
                            <tr
                                key={job.id}
                                className={`clickable-row${job.my_match != null ? ' has-match' : ''}`}
                            >
                                <td className="cell-strong">
                                    {job.position}
                                    {/* Nur für Rolle 'user' gesetzt (api/jobs.py, list_jobs) */}
                                    {job.my_match != null && (
                                        <span
                                            className="my-match-chip"
                                            title="Mindestens einer deiner Lebensläufe passt zu dieser Stelle"
                                        >
                                            <i className="fa-solid fa-diagram-project" />{' '}
                                            Passt zu dir ·{' '}
                                            {(job.my_match * 100).toFixed(0)} %
                                        </span>
                                    )}
                                </td>
                                <td>{job.customer_name}</td>
                                <td className="nowrap">
                                    {[job.zip, job.city]
                                        .filter(Boolean)
                                        .join(' ') || '-'}
                                </td>
                                <td className="nowrap">{formatDate(job.valid_until)}</td>
                                <td>
                                    <span
                                        className={`status-chip ${status.key}`}
                                    >
                                        {status.label}
                                    </span>
                                </td>
                                <td>
                                    <div className="row-actions">
                                        <Link
                                            className="row-link"
                                            to={`/jobs/${job.id}/edit`}
                                        >
                                            <i
                                                className={`fa-solid ${rowCanManage ? 'fa-pen' : 'fa-eye'}`}
                                            />{' '}
                                            {rowCanManage
                                                ? 'Bearbeiten'
                                                : 'Ansehen'}
                                        </Link>
                                        {rowCanManage && onDelete && (
                                            <button
                                                type="button"
                                                className="link-button"
                                                onClick={() => onDelete(job.id)}
                                            >
                                                <i className="fa-solid fa-trash" />{' '}
                                                Löschen
                                            </button>
                                        )}
                                    </div>
                                </td>
                            </tr>
                        )
                    })}
                </tbody>
            </table>
        </div>
    )
}
