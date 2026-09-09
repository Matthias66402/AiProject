import { Link } from 'react-router-dom'

export default function UserTable({ users }) {
  return (
    <table className="user-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Kurzname</th>
          <th>E-Mail</th>
          <th>Rolle</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {users.length === 0 && (
          <tr>
            <td colSpan={5}>Noch keine Nutzer angelegt.</td>
          </tr>
        )}
        {users.map((user) => (
          <tr key={user.id}>
            <td>
              {user.first_name} {user.last_name}
            </td>
            <td>{user.short_name}</td>
            <td>{user.email}</td>
            <td>{user.role}</td>
            <td>
              <Link to={`/users/${user.id}/edit`}>Bearbeiten</Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
