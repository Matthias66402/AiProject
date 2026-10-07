import { useEffect, useRef } from 'react'
import Quill from 'quill'
import DOMPurify from 'dompurify'
import 'quill/dist/quill.snow.css'

const TOOLBAR_OPTIONS = [
    [{ header: [false, 3, 4] }],
    ['bold', 'italic', 'underline'],
    [{ list: 'ordered' }, { list: 'bullet' }],
    ['link'],
    ['clean'],
]

// HTML immer über Quills Clipboard-Import laden statt per root.innerHTML: Quill 2
// kennt Listen intern nur als <ol><li data-list=...> und verwirft ein direkt
// gesetztes <ul> samt Inhalt (z.B. 'Deine Aufgaben' aus KI-Extrakt/-Generierung).
function setHtml(quill, html) {
    const delta = quill.clipboard.convert({
        html: DOMPurify.sanitize(html || ''),
    })
    quill.setContents(delta, 'silent')
}

// Semantisches HTML (<ul>/<ol> statt Quill-interner data-list-Attribute) - so
// wie es auch die KI liefert. Quill 2.0.3 macht dabei aus jedem Leerzeichen ein
// &nbsp;, das wird zurückgesetzt.
function getHtml(quill) {
    if (quill.getText().trim() === '') return ''
    return quill.getSemanticHTML().replaceAll('&nbsp;', ' ')
}

export default function RichTextEditor({ value, onChange }) {
    const containerRef = useRef(null)
    const quillRef = useRef(null)
    const onChangeRef = useRef(onChange)
    onChangeRef.current = onChange
    // Zuletzt geladener/gemeldeter Wert - verhindert, dass das eigene onChange
    // über value zurückkommt und den Editor (samt Cursor) neu lädt.
    const lastHtmlRef = useRef(null)

    useEffect(() => {
        // Quill mutates its target node in place and inserts the toolbar as a
        // sibling, with no built-in destroy(). A dedicated child node (cleared
        // wholesale on unmount) keeps StrictMode's mount/unmount/remount cycle
        // from leaving a second toolbar+editor behind.
        const wrapper = containerRef.current
        const editorEl = document.createElement('div')
        wrapper.appendChild(editorEl)

        const quill = new Quill(editorEl, {
            theme: 'snow',
            modules: { toolbar: TOOLBAR_OPTIONS },
        })
        setHtml(quill, value)
        lastHtmlRef.current = value || ''
        quill.on('text-change', () => {
            const html = getHtml(quill)
            lastHtmlRef.current = html
            onChangeRef.current(html)
        })
        quillRef.current = quill
        return () => {
            quillRef.current = null
            wrapper.innerHTML = ''
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    useEffect(() => {
        const quill = quillRef.current
        if (!quill || quill.hasFocus()) return
        const next = value || ''
        if (next === lastHtmlRef.current) return
        setHtml(quill, next)
        lastHtmlRef.current = next
    }, [value])

    return (
        <div className="rich-text-editor">
            <div ref={containerRef} />
        </div>
    )
}
