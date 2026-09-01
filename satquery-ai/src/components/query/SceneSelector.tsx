// Scene Selector — demo scenario cards + image metadata panels

import { useState } from 'react';
import { Activity, Layers, Cloud, Calendar, Gauge, Satellite, CheckCircle2, AlertTriangle } from 'lucide-react';
import type { DemoScenario } from '../../types';

interface SceneSelectorProps {
  scenarios: DemoScenario[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const DEMO_ICONS = [Activity, Layers, Cloud];
const DEMO_ACCENT = ['bg-navy-100 text-rs-navy', 'bg-teal-50 text-rs-teal', 'bg-orange-50 text-rs-orange'];

export default function SceneSelector({ scenarios, selectedId, onSelect }: SceneSelectorProps) {
  return (
    <div className="space-y-3">
      {scenarios.map((s, idx) => {
        const Icon = DEMO_ICONS[idx] || Activity;
        const selected = s.scenario_id === selectedId;
        return (
          <button
            key={s.scenario_id}
            onClick={() => onSelect(s.scenario_id)}
            className={`w-full text-left p-4 rounded-xl border-2 transition-all group ${
              selected
                ? 'border-rs-navy bg-navy-50'
                : 'border-rs-border bg-white hover:border-navy-200 hover:shadow-sm'
            }`}
          >
            <div className="flex items-start gap-3">
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${DEMO_ACCENT[idx]}`}>
                <Icon size={18} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="font-semibold text-sm text-rs-text-primary truncate">{s.title}</span>
                  {selected && <CheckCircle2 size={14} className="text-rs-navy flex-shrink-0" />}
                </div>
                <p className="text-xs text-rs-text-secondary leading-snug">{s.description}</p>
                <div className="flex flex-wrap gap-1 mt-2">
                  {s.images.map((img, i) => (
                    <span key={i} className="badge badge-gray text-[10px]">
                      {img.sensor} · {img.image_type}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}


// Image Metadata Panel
interface ImageMetaPanelProps {
  images: DemoScenario['images'];
  thumbnails?: string[];
}

export function ImageMetaPanel({ images, thumbnails = [] }: ImageMetaPanelProps) {
  return (
    <div className="space-y-3">
      {images.map((img, i) => (
        <div key={img.image_id} className="panel overflow-hidden">
          {/* Thumbnail */}
          {thumbnails[i] ? (
            <div className="relative">
              <img
                src={`data:image/png;base64,${thumbnails[i]}`}
                alt={img.filename || `Image ${i + 1}`}
                className="w-full h-28 object-cover"
              />
              <div className="absolute top-2 left-2">
                <span className="badge badge-red bg-red-600 text-white text-[10px] px-1.5 py-0.5 rounded uppercase font-bold tracking-wider">DEMO</span>
              </div>
              <div className="absolute top-2 right-2">
                <span className={`badge text-xs font-medium ${img.image_type === 'SAR' ? 'badge-navy' : 'badge-teal'}`}>
                  {img.image_type}
                </span>
              </div>
            </div>
          ) : (
            <div className="w-full h-20 bg-gradient-to-br from-navy-100 to-teal-50 flex items-center justify-center">
              <Satellite size={24} className="text-rs-navy opacity-30" />
            </div>
          )}

          <div className="p-3 space-y-1.5">
            <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
              <MetaRow icon={<Satellite size={11} />} label="Sensor" value={img.sensor} />
              <MetaRow icon={<Calendar size={11} />} label="Date" value={img.acquisition_date} />
              <MetaRow icon={<Gauge size={11} />} label="Resolution" value={`${img.resolution_m}m`} />
              <MetaRow icon={<Cloud size={11} />} label="Cloud" value={`${img.cloud_coverage_pct}%`} />
            </div>

            <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-medium ${
              img.cloud_status === 'Clear' || img.cloud_status === 'N/A (SAR)'
                ? 'bg-green-50 text-green-700'
                : img.cloud_status === 'Detected'
                ? 'bg-orange-50 text-orange-700'
                : 'bg-blue-50 text-blue-700'
            }`}>
              {img.cloud_status === 'Clear' || img.cloud_status === 'N/A (SAR)'
                ? <CheckCircle2 size={11} />
                : <AlertTriangle size={11} />
              }
              {img.cloud_status} · {img.processing_status}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function MetaRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-1">
      <span className="text-rs-text-muted mt-0.5">{icon}</span>
      <div>
        <span className="text-[10px] text-rs-text-muted block uppercase tracking-wide leading-none mb-0.5">{label}</span>
        <span className="text-xs font-medium text-rs-text-primary">{value}</span>
      </div>
    </div>
  );
}
