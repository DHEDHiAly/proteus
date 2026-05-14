const STORAGE_KEY = 'proteus_saved_designs';

export interface SavedDesign {
  id: string;
  savedAt: string;
  name: string;
  target: string;
  sequence: string;
  bindingScore: number;
  kd_nM?: number;
  stabilityScore: number;
  solubilityScore: number;
  totalEnergy?: number;
  labViabilityScore?: number;
  selectivityRatio?: number;
  serumHalfLifeMin?: number;
  patient?: { cancerType: string; cancerStage: string };
}

export const savedDesignsService = {
  getAll(): SavedDesign[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as SavedDesign[]) : [];
    } catch {
      return [];
    }
  },

  save(design: Omit<SavedDesign, 'id' | 'savedAt'>): SavedDesign {
    const all = this.getAll();
    const saved: SavedDesign = {
      ...design,
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      savedAt: new Date().toISOString(),
    };
    all.unshift(saved);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
    return saved;
  },

  delete(id: string): void {
    const all = this.getAll().filter((d) => d.id !== id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
  },

  exportFasta(design: SavedDesign): void {
    const header = `>Proteus|${design.target}|${design.name}|saved:${design.savedAt.slice(0, 10)}`;
    const blob = new Blob([`${header}\n${design.sequence}\n`], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `proteus-${design.target.replace(/\s+/g, '_')}-${design.id.slice(0, 6)}.fasta`;
    a.click();
  },
};
