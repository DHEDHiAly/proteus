interface PDBeViewerProps {
  pdbId: string
  mutations?: { position: number; from: string; to: string }[]
  height?: number
}

export default function PDBeViewer({ pdbId, mutations, height = 400 }: PDBeViewerProps) {
  const embedUrl = `https://embed.rcsb.org/3d/${pdbId}?style=stick&color=spectrum&showControls=true`

  return (
    <div className="card overflow-hidden">
      <h3 className="text-lg font-semibold mb-4">3D Structure Viewer</h3>
      <div className="relative rounded-lg overflow-hidden border border-gray-200">
        <iframe
          src={embedUrl}
          style={{ width: '100%', height, border: 'none' }}
          title={`PDB ${pdbId} structure`}
          allowFullScreen
        />
      </div>
      {mutations && mutations.length > 0 && (
        <div className="mt-3 space-y-1">
          <p className="text-xs font-medium text-gray-500">Designed mutations:</p>
          <div className="flex flex-wrap gap-1.5">
            {mutations.map((m, i) => (
              <span
                key={i}
                className="inline-flex items-center space-x-1 px-2 py-0.5 bg-red-50 text-red-700 rounded text-xs font-mono"
              >
                <span>{m.from}</span>
                <span className="text-gray-400">{m.position}</span>
                <span>{m.to}</span>
              </span>
            ))}
          </div>
        </div>
      )}
      <p className="mt-2 text-xs text-gray-400">
        <a href={`https://www.rcsb.org/structure/${pdbId}`} target="_blank" rel="noopener noreferrer" className="underline">
          View on RCSB PDB
        </a>
      </p>
    </div>
  )
}
