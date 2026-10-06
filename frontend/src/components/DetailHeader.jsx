import { Link } from 'react-router-dom'

// Kopfbereich der Detailseiten (Stelle, Stellenanbieter, Nutzer): Zurück-Link,
// Titel mit Meta-Zeile links, Aktionen rechts.
export default function DetailHeader({ backTo, backLabel, onBack, title, meta, actions }) {
    return (
        <div className="detail-header">
            {backTo && (
                <Link className="detail-back" to={backTo}>
                    <i className="fa-solid fa-chevron-left" /> {backLabel}
                </Link>
            )}
            {onBack && (
                <button type="button" className="detail-back" onClick={onBack}>
                    <i className="fa-solid fa-chevron-left" /> {backLabel}
                </button>
            )}
            <div className="detail-title-row">
                <div className="detail-title">
                    <h1>{title}</h1>
                    {meta && <div className="detail-meta">{meta}</div>}
                </div>
                {actions && <div className="detail-actions">{actions}</div>}
            </div>
        </div>
    )
}
