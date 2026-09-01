// Visual outputs — before/after slider, change map, image grid

import { useState, useRef, useCallback } from 'react';
import { Layers, Image as ImageIcon } from 'lucide-react';
import type { VisualOutput } from '../../types';

// ─── Before/After Slider ──────────────────────────────────────────────────────

interface BeforeAfterSliderProps {
  beforeB64: string;
  afterB64: string;
  beforeLabel?: string;
  afterLabel?: string;
}

export function BeforeAfterSlider({
  beforeB64, afterB64,
  beforeLabel = 'Before', afterLabel = 'After',
}: BeforeAfterSliderProps) {
  const [pos, setPos] = useState(50);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const updatePos = useCallback((clientX: number) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const pct = ((clientX - rect.left) / rect.width) * 100;
    setPos(Math.max(5, Math.min(95, pct)));
  }, []);

  return (
    <div
      ref={containerRef}
      className="image-compare-container rounded-xl overflow-hidden select-none"
      style={{ height: '240px' }}
      onMouseDown={e => { isDragging.current = true; updatePos(e.clientX); }}
      onMouseMove={e => isDragging.current && updatePos(e.clientX)}
      onMouseUp={() => { isDragging.current = false; }}
      onMouseLeave={() => { isDragging.current = false; }}
    >
      {/* After (background) */}
      <img
        src={`data:image/png;base64,${afterB64}`}
        alt={afterLabel}
        className="absolute inset-0 w-full h-full object-cover"
        draggable={false}
      />
      <div className="absolute top-2 right-2 badge badge-navy text-[10px] z-10">{afterLabel}</div>

      {/* Before (clipped) */}
      <div
        className="absolute inset-0 overflow-hidden"
        style={{ width: `${pos}%` }}
      >
        <img
          src={`data:image/png;base64,${beforeB64}`}
          alt={beforeLabel}
          className="absolute inset-0 h-full object-cover"
          style={{ width: `${100 / (pos / 100)}%`, maxWidth: 'none' }}
          draggable={false}
        />
        <div className="absolute top-2 left-2 badge badge-teal text-[10px] z-10">{beforeLabel}</div>
      </div>

      {/* Handle */}
      <div
        className="image-compare-handle"
        style={{ left: `calc(${pos}% - 1.5px)` }}
      >
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 bg-white rounded-full shadow-lg flex items-center justify-center">
          <div className="flex gap-0.5">
            <div className="w-0.5 h-4 bg-gray-400 rounded" />
            <div className="w-0.5 h-4 bg-gray-400 rounded" />
          </div>
        </div>
      </div>

      {/* Drag hint */}
      <div className="absolute bottom-2 left-1/2 -translate-x-1/2 text-[10px] text-white bg-black/40 px-2 py-0.5 rounded-full">
        drag to compare
      </div>
    </div>
  );
}

// ─── Image Card ───────────────────────────────────────────────────────────────

interface ImageCardProps {
  output: VisualOutput;
}

export function ImageCard({ output }: ImageCardProps) {
  const typeColors: Record<string, string> = {
    change_map: 'badge-red',
    confidence_heatmap: 'badge-orange',
    sar_image: 'badge-navy',
    reconstructed: 'badge-green',
    scene_overview: 'badge-teal',
    cloud_overlay: 'badge-orange',
    before: 'badge-gray',
    after: 'badge-navy',
    optical: 'badge-teal',
    sar: 'badge-navy',
  };

  return (
    <div className="panel overflow-hidden group">
      <div className="relative overflow-hidden">
        <img
          src={`data:image/png;base64,${output.b64}`}
          alt={output.label}
          className="w-full object-cover transition-transform duration-300 group-hover:scale-105"
          style={{ height: '160px' }}
        />
        <div className="absolute top-2 left-2">
          <span className={`badge text-[10px] font-bold uppercase tracking-wide ${typeColors[output.type] || 'badge-gray'}`}>
            {output.type.replace(/_/g, ' ')}
          </span>
        </div>
        <div className="absolute top-2 right-2">
          <span className="badge badge-red text-[10px] font-bold bg-red-600 text-white uppercase">DEMO</span>
        </div>
      </div>
      <div className="px-3 py-2">
        <p className="text-xs font-semibold text-rs-text-primary">{output.label}</p>
      </div>
    </div>
  );
}

// ─── Visual Outputs Grid ──────────────────────────────────────────────────────

interface VisualOutputsGridProps {
  outputs: VisualOutput[];
}

export default function VisualOutputsGrid({ outputs }: VisualOutputsGridProps) {
  // Find before/after for slider
  const before = outputs.find(o => o.type === 'before');
  const after = outputs.find(o => o.type === 'after');
  const others = outputs.filter(o => o.type !== 'before' && o.type !== 'after');

  if (outputs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-40 text-rs-text-muted">
        <ImageIcon size={28} className="mb-2 opacity-40" />
        <p className="text-sm">Visual outputs will appear after analysis</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Before/After slider if both exist */}
      {before && after && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Layers size={14} className="text-rs-text-muted" />
            <span className="section-label">Before / After Comparison</span>
          </div>
          <BeforeAfterSlider
            beforeB64={before.b64}
            afterB64={after.b64}
            beforeLabel={before.label}
            afterLabel={after.label}
          />
        </div>
      )}

      {/* Other outputs */}
      {others.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <ImageIcon size={14} className="text-rs-text-muted" />
            <span className="section-label">Analysis Outputs</span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {others.map((o, i) => (
              <ImageCard key={i} output={o} />
            ))}
          </div>
        </div>
      )}

      {/* Optical/SAR side-by-side */}
      {!before && !after && outputs.filter(o => ['optical', 'sar'].includes(o.type)).length >= 2 && (
        <div className="grid grid-cols-2 gap-3">
          {outputs.map((o, i) => <ImageCard key={i} output={o} />)}
        </div>
      )}
    </div>
  );
}
