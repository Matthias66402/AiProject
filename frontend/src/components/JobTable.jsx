import { Link } from 'react-router-dom'

export default function JobTable({
    jobs,
    isAdmin,
    isCustomerUser,
    currentCustomerId,
    onDelete,
}) {
    return (
        <table className="user-table">
            <thead>
                <tr>
                    <th>Position</th>
                    <th>Kunde</th>
                    <th>Gültig von</th>
                    <th>Gültig bis</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                {jobs.length === 0 && (
                    <tr>
                        <td colSpan={5}>Noch keine Stelle angelegt.</td>
                    </tr>
                )}
                {jobs.map((job) => {
                    const rowCanManage =
                        isAdmin ||
                        (isCustomerUser &&
                            job.customer_id === currentCustomerId)
                    return (
                        <tr key={job.id} className="clickable-row">
                            <td>{job.position}</td>
                            <td>{job.customer_name}</td>
                            <td>{job.valid_from || '-'}</td>
                            <td>{job.valid_until || '-'}</td>
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
    )
}
