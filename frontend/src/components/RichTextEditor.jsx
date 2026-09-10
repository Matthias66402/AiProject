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

export default function RichTextEditor({ value, onChange }) {
    const containerRef = useRef(null)
    const quillRef = useRef(null)
    const onChangeRef = useRef(onChange)
    onChangeRef.current = onChange

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
        quill.root.innerHTML = DOMPurify.sanitize(value || '')
        quill.on('text-change', () => {
            const html =
                quill.getText().trim() === '' ? '' : quill.root.innerHTML
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
        const current = quill.root.innerHTML
        const next = DOMPurify.sanitize(value || '')
        if (current !== next) quill.root.innerHTML = next
    }, [value])

    return (
        <div className="rich-text-editor">
            <div ref={containerRef} />
        </div>
    )
}
