import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function ManualContentViewer({ chunks }) {
  if (chunks.length === 0) {
    return <div className="manual-content-viewer__empty">아직 처리 중이거나 내용이 없습니다.</div>
  }

  const blocks = chunks.reduce((acc, chunk) => {
    const prevTitle = acc.length > 0 ? acc[acc.length - 1].title : null
    const showTitle = Boolean(chunk.section_title) && chunk.section_title !== prevTitle
    acc.push({ chunk, showTitle, title: chunk.section_title || prevTitle })
    return acc
  }, [])

  return (
    <div className="manual-content-viewer">
      {blocks.map(({ chunk, showTitle }) => (
        <div key={chunk.chunk_index} className="manual-content-viewer__block">
          {showTitle && <h4 className="manual-content-viewer__section">{chunk.section_title}</h4>}
          <div className="manual-content-viewer__text">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{chunk.content}</ReactMarkdown>
          </div>
        </div>
      ))}
    </div>
  )
}
