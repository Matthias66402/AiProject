import { createContext, useCallback, useContext, useEffect, useState } from 'react'

const ConfirmContext = createContext(null)

// Ersatz für window.confirm(): liefert statt eines synchronen Rückgabewerts
// ein Promise<boolean>, das beim Klick auf Löschen/Abbrechen (oder Escape/
// Klick auf den Hintergrund, beides = Abbrechen) aufgelöst wird. Ein
// einzelnes Modal für die ganze App (siehe App.jsx), statt es in jeder
// Seite mit Lösch-Aktion neu zu bauen.
export function ConfirmProvider({ children }) {
    const [dialog, setDialog] = useState(null)

    const confirm = useCallback((message) => {
        return new Promise((resolve) => {
            setDialog({ message, resolve })
        })
    }, [])

    function settle(result) {
        dialog?.resolve(result)
        setDialog(null)
    }

    useEffect(() => {
        if (!dialog) return
        function onKeyDown(e) {
            if (e.key === 'Escape') settle(false)
        }
        document.addEventListener('keydown', onKeyDown)
        return () => document.removeEventListener('keydown', onKeyDown)
    }, [dialog])

    return (
        <ConfirmContext.Provider value={confirm}>
            {children}
            {dialog && (
                <div
                    className="confirm-overlay"
                    onClick={() => settle(false)}
                >
                    <div
                        className="confirm-dialog"
                        role="alertdialog"
                        aria-modal="true"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <p>{dialog.message}</p>
                        <div className="confirm-actions">
                            <button
                                type="button"
                                className="subtle-btn cancel cancel-link"
                                onClick={() => settle(false)}
                                autoFocus
                            >
                                <i className="fa-solid fa-xmark" /> Abbrechen
                            </button>
                            <button
                                type="button"
                                className="confirm-danger-btn"
                                onClick={() => settle(true)}
                            >
                                <i className="fa-solid fa-trash" /> Löschen
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </ConfirmContext.Provider>
    )
}

export function useConfirm() {
    const confirm = useContext(ConfirmContext)
    if (!confirm) {
        throw new Error('useConfirm muss innerhalb von ConfirmProvider aufgerufen werden')
    }
    return confirm
}
