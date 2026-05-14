import { useEffect, useRef } from 'react';

interface MolStarViewerProps {
  pdbId: string;
  mutations?: { position: number; from: string; to: string }[];
  highlightResidues?: number[];
  height?: number;
  onReady?: () => void;
}

export default function MolStarViewer({
  pdbId,
  mutations = [],
  highlightResidues = [],
  height = 500,
  onReady,
}: MolStarViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !pdbId) return;
    const el = containerRef.current;

    const resi = mutations.map((m) => m.position);
    const mutStr = mutations.map((m) => `${m.from}${m.position}${m.to}`).join(', ');

    el.innerHTML = `
      <div style="display:flex;flex-direction:column;height:${height}px;background:#000;border-radius:8px;overflow:hidden">
        <iframe
          src="https://www.rcsb.org/3d-view/${pdbId}?style=stick&color=spectrum"
          style="width:100%;height:100%;border:none;background:#000"
          title="3D structure"
          onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"
        />
        <div style="display:none;flex:1;align-items:center;justify-content:center;color:#666;font-size:13px;flex-direction:column;gap:8px">
          <span>3D Structure — ${pdbId.toUpperCase()}</span>
          ${mutations.length > 0 ? `<span style="color:#f87171;font-size:11px">Mutations: ${mutStr}</span>` : ''}
          <a href="https://www.rcsb.org/structure/${pdbId}" target="_blank" rel="noopener noreferrer" style="color:#666;font-size:11px;text-decoration:underline">
            View on RCSB.org →
          </a>
        </div>
        <div style="display:flex;gap:8px;padding:6px 8px;flex-wrap:wrap;border-top:1px solid #1a1a1a">
          ${resi.length > 0 ? `<span style="font-size:10px;color:#f87171;background:#1a1a1a;padding:1px 8px;border-radius:4px">● ${resi.length} mutation${resi.length > 1 ? 's' : ''}</span>` : ''}
          ${highlightResidues.length > 0 ? `<span style="font-size:10px;color:#fbbf24;background:#1a1a1a;padding:1px 8px;border-radius:4px">● ${highlightResidues.length} binding site</span>` : ''}
          <a href="https://www.rcsb.org/structure/${pdbId}" target="_blank" rel="noopener noreferrer" style="font-size:9px;color:#444;text-decoration:underline;margin-left:auto;padding-top:1px">RCSB</a>
        </div>
      </div>`;
    onReady?.();
  }, [pdbId, mutations, highlightResidues, height]);

  return <div ref={containerRef} />;
}
