import { useRef, useState, useCallback, useEffect } from 'react';

interface WidgetProps {
  id: string;
  title: string;
  icon?: string;
  children: React.ReactNode;
  defaultVisible?: boolean;
  onClose?: (id: string) => void;
  onMinimize?: (id: string) => void;
  onFullscreen?: (id: string) => void;
  isFullscreen?: boolean;
  isMinimized?: boolean;
  className?: string;
}

export default function WidgetContainer({
  id, title, icon, children, onClose, onMinimize, onFullscreen,
  isFullscreen, isMinimized, className = '',
}: WidgetProps) {
  const headerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  if (isMinimized) return null;

  return (
    <div
      className={`flex flex-col rounded-xl border border-[#222] bg-[#0a0a0a] overflow-hidden ${isFullscreen ? 'fixed inset-4 z-50' : ''} ${className}`}
      role="region"
      aria-label={title}
    >
      <div
        ref={headerRef}
        className="flex items-center justify-between px-3 py-2 bg-[#111] border-b border-[#222] cursor-grab active:cursor-grabbing select-none"
        style={{ minHeight: 36 }}
      >
        <div className="flex items-center space-x-2">
          {icon && <span className="text-[11px] text-gray-500">{icon}</span>}
          <span className="text-[11px] font-medium text-gray-300 uppercase tracking-wider">{title}</span>
        </div>
        <div className="flex items-center space-x-1">
          {onMinimize && (
            <button onClick={() => onMinimize(id)}
              className="w-5 h-5 flex items-center justify-center rounded hover:bg-white/10 text-gray-500 hover:text-white transition-colors text-[10px]"
              aria-label={`Minimize ${title}`}>─</button>
          )}
          {onFullscreen && (
            <button onClick={() => onFullscreen(id)}
              className="w-5 h-5 flex items-center justify-center rounded hover:bg-white/10 text-gray-500 hover:text-white transition-colors text-[10px]"
              aria-label={`Fullscreen ${title}`}>↗</button>
          )}
          {onClose && (
            <button onClick={() => onClose(id)}
              className="w-5 h-5 flex items-center justify-center rounded hover:bg-white/10 text-gray-500 hover:text-white transition-colors text-[10px]"
              aria-label={`Close ${title}`}>✕</button>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-auto p-3">{children}</div>
      <div className="h-2 cursor-se-resize bg-transparent hover:bg-white/5 transition-colors" />
    </div>
  );
}

export function useWidgetLayout(defaultLayouts: Record<string, { x: number; y: number; w: number; h: number; visible: boolean }>) {
  const STORAGE_KEY = 'proteus-widget-layout';
  const [layouts, setLayouts] = useState<Record<string, any>>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : defaultLayouts;
    } catch { return defaultLayouts; }
  });

  const [fullscreenWidget, setFullscreenWidget] = useState<string | null>(null);

  const updateLayout = useCallback((id: string, updates: any) => {
    setLayouts((prev: any) => {
      const next = { ...prev, [id]: { ...prev[id], ...updates } };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const toggleVisibility = useCallback((id: string) => {
    updateLayout(id, { visible: !layouts[id]?.visible });
  }, [layouts, updateLayout]);

  const toggleFullscreen = useCallback((id: string) => {
    setFullscreenWidget((prev) => prev === id ? null : id);
  }, []);

  const resetLayout = useCallback(() => {
    setLayouts(defaultLayouts);
    localStorage.removeItem(STORAGE_KEY);
  }, [defaultLayouts]);

  const savePreset = useCallback((name: string) => {
    const presets = JSON.parse(localStorage.getItem('proteus-layout-presets') || '{}');
    presets[name] = layouts;
    localStorage.setItem('proteus-layout-presets', JSON.stringify(presets));
  }, [layouts]);

  const loadPreset = useCallback((name: string) => {
    const presets = JSON.parse(localStorage.getItem('proteus-layout-presets') || '{}');
    if (presets[name]) {
      setLayouts(presets[name]);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(presets[name]));
    }
  }, []);

  return {
    layouts, fullscreenWidget, updateLayout,
    toggleVisibility, toggleFullscreen, resetLayout,
    savePreset, loadPreset,
  };
}
