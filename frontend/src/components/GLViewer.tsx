import { useEffect, useRef } from 'react';

interface Mutation {
  position: number;
  from: string;
  to: string;
}

interface GLViewerProps {
  pdbId: string;
  sequence?: string;
  seed?: string;
  mutations?: Mutation[];
  height?: number;
}

declare global {
  interface Window {
    $3Dmol: any;
  }
}

const SCRIPT_ID = 'threedmol-script';

export default function GLViewer({ pdbId, sequence, seed, mutations, height = 400 }: GLViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const loadScript = () => {
      if (document.getElementById(SCRIPT_ID)) {
        initViewer();
        return;
      }
      const script = document.createElement('script');
      script.id = SCRIPT_ID;
      script.src = 'https://3Dmol.csb.pitt.edu/build/3Dmol-min.js';
      script.onload = initViewer;
      document.body.appendChild(script);
    };

    function initViewer() {
      if (!containerRef.current || !window.$3Dmol) return;
      const el = containerRef.current;
      el.innerHTML = '';

      try {
        const viewer = window.$3Dmol.createViewer(el, {
          backgroundColor: 'black',
          antialiasing: true,
        });
        viewerRef.current = viewer;

        viewer.addModel('', 'pdb');

        const url = `https://files.rcsb.org/download/${pdbId}.pdb`;
        fetch(url)
          .then((res) => res.text())
          .then((pdbData: string) => {
            viewer.removeAllModels();
            viewer.addModel(pdbData, 'pdb');
            viewer.setStyle({}, {
              cartoon: { color: 'spectrum' },
            });
            viewer.setStyle({ hetflag: false }, {
              cartoon: { color: 'white' },
            });

            if (mutations && mutations.length > 0) {
              const resi = mutations.map((m) => m.position);
              viewer.setStyle({ resi: resi }, {
                stick: { radius: 0.3, color: 'red' },
                cartoon: { color: 'red' },
              });
            }

            viewer.zoomTo();
            viewer.render();
          })
          .catch(() => {
            el.innerHTML = '<div style="padding:40px;text-align:center;color:#666;font-size:13px">Could not load PDB structure.</div>';
          });
      } catch (e) {
        el.innerHTML = '<div style="padding:40px;text-align:center;color:#666;font-size:13px">3D viewer unavailable</div>';
      }
    }

    loadScript();

    return () => {
      if (viewerRef.current) {
        try { viewerRef.current.clear(); } catch {}
        viewerRef.current = null;
      }
    };
  }, [pdbId, mutations]);

  return (
    <div>
      <div
        ref={containerRef}
        style={{ width: '100%', height, borderRadius: 8 }}
      />
      {mutations && mutations.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {mutations.map((m, i) => (
            <span key={i} className="text-[10px] font-mono bg-white/10 text-white/80 px-1.5 py-0.5 rounded">
              {m.from}{m.position}{m.to}
            </span>
          ))}
        </div>
      )}
      <p className="text-[10px] text-gray-600 mt-1.5">
        <a href={`https://www.rcsb.org/structure/${pdbId}`} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">
          View on RCSB.org
        </a>
      </p>
    </div>
  );
}
