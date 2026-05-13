import { useEffect, useRef } from 'react'

interface PDBeViewerProps {
  pdbId: string
  mutations?: { position: number; from: string; to: string }[]
  height?: number
}

declare global {
  interface Window {
    PDBeMolstarPlugin: any
  }
}

export default function PDBeViewer({ pdbId, mutations, height = 400 }: PDBeViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerInstance = useRef<any>(null)

  useEffect(() => {
    if (!containerRef.current || !pdbId) return

    const scriptId = 'pdbe-molstar-script'
    if (!document.getElementById(scriptId)) {
      const script = document.createElement('script')
      script.id = scriptId
      script.src = 'https://cdn.jsdelivr.net/npm/pdbe-molstar@1.3.0/dist/pdbe-molstar-plugin.js'
      script.onload = initViewer
      document.body.appendChild(script)
    } else if (window.PDBeMolstarPlugin) {
      initViewer()
    }

    function initViewer() {
      if (!containerRef.current || !window.PDBeMolstarPlugin) return

      const options = {
        moleculeId: pdbId,
        showControls: true,
        hideCanvasControls: false,
        bgColor: { r: 255, g: 255, b: 255 },
      }

      try {
        viewerInstance.current = new window.PDBeMolstarPlugin()
        viewerInstance.current.render(containerRef.current, options)

        setTimeout(() => {
          highlightMutations()
        }, 2000)
      } catch (e) {
        console.error('Failed to initialize PDBe Molstar:', e)
      }
    }

    function highlightMutations() {
      if (!mutations || mutations.length === 0 || !viewerInstance.current) return
      try {
        const residueIds = mutations.map((m) => m.position).join(',')
        viewerInstance.current.visual.select({
          data: [
            {
              struct: `residues ${residueIds}`,
              color: { r: 255, g: 0, b: 0 },
              label: 'Designed Mutations',
            },
          ],
        })
      } catch (e) {
        console.error('Failed to highlight mutations:', e)
      }
    }

    return () => {
      viewerInstance.current = null
    }
  }, [pdbId, mutations])

  if (!pdbId) {
    return (
      <div className="card flex items-center justify-center" style={{ height }}>
        <p className="text-gray-500">No PDB structure available</p>
      </div>
    )
  }

  return (
    <div className="card overflow-hidden">
      <h3 className="text-lg font-semibold mb-4">3D Structure Viewer</h3>
      <div
        ref={containerRef}
        style={{ width: '100%', height }}
        className="rounded-lg border border-gray-200"
      />
      {mutations && mutations.length > 0 && (
        <div className="mt-3 text-xs text-gray-500">
          <span className="font-medium">Mutations highlighted:</span>{' '}
          {mutations.map((m, i) => (
            <span key={i} className="mr-2">
              {m.from}{m.position}{m.to}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
