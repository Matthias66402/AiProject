import { Link } from 'react-router-dom'

export default function CustomerTable({
    customers,
    isAdmin,
    isCustomerUser,
    currentCustomerId,
    onDelete,
}) {
    return (
        <table className="user-table">
            <thead>
                <tr>
                    <th>Firma</th>
                    <th>Adresse</th>
                    <th>PLZ</th>
                    <th>Stadt</th>
                    <th>Angelegt am</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                {customers.length === 0 && (
                    <tr>
                        <td colSpan={6}>Noch keine Kunden angelegt.</td>
                    </tr>
                )}
                {customers.map((customer) => {
                    const rowCanManage =
                        isAdmin ||
                        (isCustomerUser && customer.id === currentCustomerId)
                    return (
                        <tr key={customer.id} className="clickable-row">
                            <td>{customer.company_name}</td>
                            <td>
                                {customer.street} {customer.street_number}
                            </td>
                            <td>{customer.zip}</td>
                            <td>{customer.city}</td>
                            <td>
                                {customer.created_at
                                    ? customer.created_at.slice(0, 10)
                                    : '-'}
                            </td>
                            <td>
                                <div className="row-actions">
                                    <Link
                                        className="row-link"
                                        to={`/customers/${customer.id}/edit`}
                                    >
                                        <i
                                            className={`fa-solid ${rowCanManage ? 'fa-pen' : 'fa-eye'}`}
                                        />{' '}
                                        {rowCanManage
                                            ? 'Bearbeiten'
                                            : 'Ansehen'}
                                    </Link>
                                    {isAdmin && onDelete && (
                                        <button
                                            type="button"
                                            className="link-button"
                                            onClick={() =>
                                                onDelete(customer.id)
                                            }
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
