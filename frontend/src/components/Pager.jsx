export default function Pager({
    page,
    totalPages,
    perPage,
    perPageOptions,
    onPageChange,
    onPerPageChange,
}) {
    return (
        <div className="pager">
            <div className="pager-nav">
                {page > 1 ? (
                    <button
                        type="button"
                        className="subtle-btn"
                        onClick={() => onPageChange(page - 1)}
                    >
                        <i className="fa-solid fa-angle-left" /> Zurück
                    </button>
                ) : (
                    <span className="subtle-btn disabled">
                        <i className="fa-solid fa-angle-left" /> Zurück
                    </span>
                )}
                <span className="pager-status">
                    Seite {page} von {totalPages}
                </span>
                {page < totalPages ? (
                    <button
                        type="button"
                        className="subtle-btn"
                        onClick={() => onPageChange(page + 1)}
                    >
                        Weiter <i className="fa-solid fa-angle-right" />
                    </button>
                ) : (
                    <span className="subtle-btn disabled">
                        Weiter <i className="fa-solid fa-angle-right" />
                    </span>
                )}
            </div>
            {/* Ohne onPerPageChange (z. B. kompakter Pager in der Seitenspalte)
                entfällt die Auswahl "Einträge pro Seite". */}
            {onPerPageChange && (
                <div className="pager-per-page">
                    <label htmlFor="per_page">Einträge pro Seite</label>
                    <select
                        id="per_page"
                        value={perPage}
                        onChange={(e) => onPerPageChange(Number(e.target.value))}
                    >
                        {perPageOptions.map((opt) => (
                            <option key={opt} value={opt}>
                                {opt}
                            </option>
                        ))}
                    </select>
                </div>
            )}
        </div>
    )
}
