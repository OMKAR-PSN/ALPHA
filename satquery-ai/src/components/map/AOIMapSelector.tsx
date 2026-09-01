// AOIMapSelector.tsx — Leaflet map for selecting an Area of Interest

import { useEffect, useRef, useState } from 'react';
import { MapPin, Square, RotateCcw, CheckCircle2 } from 'lucide-react';

// Import Leaflet lazily to avoid SSR issues
import type { Map as LeafletMap, Rectangle as LeafletRectangle, LatLngBounds } from 'leaflet';

interface AOI {
  name: string;
  bounds: [[number, number], [number, number]]; // [[south, west], [north, east]]
  center: [number, number];
  zoom: number;
}

const PRESET_AOIS: AOI[] = [
  {
    name: 'Guwahati, Assam',
    bounds: [[26.05, 91.55], [26.25, 91.85]],
    center: [26.15, 91.70],
    zoom: 12,
  },
  {
    name: 'Mumbai Metropolitan',
    bounds: [[18.85, 72.75], [19.30, 73.05]],
    center: [19.07, 72.88],
    zoom: 11,
  },
  {
    name: 'Chilika Lake, Odisha',
    bounds: [[19.50, 85.10], [19.90, 85.55]],
    center: [19.70, 85.32],
    zoom: 11,
  },
  {
    name: 'Delhi NCR Region',
    bounds: [[28.40, 76.80], [28.90, 77.40]],
    center: [28.65, 77.10],
    zoom: 11,
  },
];

export interface AOISelection {
  name: string;
  bounds: [[number, number], [number, number]];
}

interface AOIMapSelectorProps {
  onAOISelected: (aoi: AOISelection | null) => void;
  selectedAOI: AOISelection | null;
}

export default function AOIMapSelector({ onAOISelected, selectedAOI }: AOIMapSelectorProps) {
  const mapRef = useRef<LeafletMap | null>(null);
  const rectRef = useRef<LeafletRectangle | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [mapReady, setMapReady] = useState(false);
  const [isDrawing, setIsDrawing] = useState(false);
  const [activePreset, setActivePreset] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    // Dynamically import Leaflet to avoid build issues
    import('leaflet').then(L => {
      // Fix default icon paths
      // @ts-expect-error – leaflet icon hack
      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      });

      const map = L.map(containerRef.current!, {
        center: [22.5, 82.5],
        zoom: 5,
        zoomControl: true,
        attributionControl: false,
      });

      // Dark satellite-style tile layer
      L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        { maxZoom: 18 }
      ).addTo(map);

      // Light labels overlay
      L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
        { maxZoom: 18, opacity: 0.7 }
      ).addTo(map);

      // Drawing logic
      let startLatLng: L.LatLng | null = null;
      let drawingRect: L.Rectangle | null = null;
      let drawMode = false;

      map.on('mousedown', (e: L.LeafletMouseEvent) => {
        if (!drawMode) return;
        startLatLng = e.latlng;
        map.dragging.disable();
      });

      map.on('mousemove', (e: L.LeafletMouseEvent) => {
        if (!drawMode || !startLatLng) return;
        const bounds = L.latLngBounds(startLatLng, e.latlng);
        if (drawingRect) {
          drawingRect.setBounds(bounds);
        } else {
          drawingRect = L.rectangle(bounds, {
            color: '#1A6B6B',
            weight: 2,
            fillColor: '#1A6B6B',
            fillOpacity: 0.15,
            dashArray: '6,4',
          }).addTo(map);
        }
      });

      map.on('mouseup', (e: L.LeafletMouseEvent) => {
        if (!drawMode || !startLatLng) return;
        map.dragging.enable();
        const bounds = L.latLngBounds(startLatLng, e.latlng);
        if (drawingRect) {
          drawingRect.setBounds(bounds);
          rectRef.current = drawingRect;
          drawingRect = null;
        }
        startLatLng = null;
        drawMode = false;
        setIsDrawing(false);

        const sw = bounds.getSouthWest();
        const ne = bounds.getNorthEast();
        const center = bounds.getCenter();
        onAOISelected({
          name: `Custom AOI (${center.lat.toFixed(2)}°N, ${center.lng.toFixed(2)}°E)`,
          bounds: [[sw.lat, sw.lng], [ne.lat, ne.lng]],
        });
        setActivePreset(null);
      });

      // Expose drawMode toggler
      (map as unknown as { _startDraw: () => void })._startDraw = () => {
        drawMode = true;
        setIsDrawing(true);
        // Remove existing rect
        if (rectRef.current) {
          rectRef.current.remove();
          rectRef.current = null;
        }
        onAOISelected(null);
        setActivePreset(null);
      };

      mapRef.current = map;
      setMapReady(true);
    });

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  const handlePreset = (aoi: AOI) => {
    if (!mapRef.current) return;
    import('leaflet').then(L => {
      // Remove old rect
      if (rectRef.current) {
        rectRef.current.remove();
        rectRef.current = null;
      }
      const bounds = L.latLngBounds(aoi.bounds[0], aoi.bounds[1]);
      const rect = L.rectangle(bounds, {
        color: '#1A6B6B',
        weight: 2,
        fillColor: '#1A6B6B',
        fillOpacity: 0.2,
      }).addTo(mapRef.current!);
      rectRef.current = rect;
      mapRef.current!.fitBounds(bounds, { padding: [20, 20] });
      onAOISelected({ name: aoi.name, bounds: aoi.bounds });
      setActivePreset(aoi.name);
    });
  };

  const handleDraw = () => {
    const map = mapRef.current as unknown as { _startDraw: () => void };
    map?._startDraw?.();
  };

  const handleClear = () => {
    if (rectRef.current) {
      rectRef.current.remove();
      rectRef.current = null;
    }
    onAOISelected(null);
    setActivePreset(null);
    mapRef.current?.setView([22.5, 82.5], 5);
  };

  return (
    <div className="space-y-3">
      {/* Preset AOI buttons */}
      <div>
        <p className="text-[10px] font-bold uppercase tracking-widest text-rs-text-muted mb-2">Preset Regions</p>
        <div className="grid grid-cols-2 gap-1.5">
          {PRESET_AOIS.map(aoi => (
            <button
              key={aoi.name}
              onClick={() => handlePreset(aoi)}
              className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg border text-left transition-all text-xs ${
                activePreset === aoi.name
                  ? 'border-rs-teal bg-teal-50 text-rs-teal font-semibold'
                  : 'border-rs-border bg-white text-rs-text-secondary hover:border-rs-teal hover:text-rs-teal'
              }`}
            >
              <MapPin size={10} className="flex-shrink-0" />
              <span className="truncate">{aoi.name.split(',')[0]}</span>
              {activePreset === aoi.name && <CheckCircle2 size={10} className="flex-shrink-0 ml-auto" />}
            </button>
          ))}
        </div>
      </div>

      {/* Draw + Clear buttons */}
      <div className="flex gap-2">
        <button
          onClick={handleDraw}
          disabled={!mapReady}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg border text-xs font-semibold transition-all ${
            isDrawing
              ? 'bg-rs-teal text-white border-rs-teal'
              : 'bg-white border-rs-border text-rs-text-secondary hover:border-rs-teal hover:text-rs-teal'
          } disabled:opacity-50`}
        >
          <Square size={12} />
          {isDrawing ? 'Click & drag on map…' : 'Draw AOI'}
        </button>
        {selectedAOI && (
          <button
            onClick={handleClear}
            className="px-3 py-2 rounded-lg border border-rs-border text-xs text-rs-text-muted hover:border-red-300 hover:text-red-500 transition-all"
          >
            <RotateCcw size={12} />
          </button>
        )}
      </div>

      {/* Selected AOI display */}
      {selectedAOI && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-50 border border-teal-200">
          <CheckCircle2 size={13} className="text-rs-teal flex-shrink-0" />
          <div className="min-w-0">
            <p className="text-xs font-semibold text-rs-teal truncate">{selectedAOI.name}</p>
            <p className="text-[10px] text-teal-600 font-mono">
              {selectedAOI.bounds[0][0].toFixed(2)}°N–{selectedAOI.bounds[1][0].toFixed(2)}°N
            </p>
          </div>
        </div>
      )}

      {/* Map container */}
      <div className="relative rounded-xl overflow-hidden border border-rs-border" style={{ height: '220px' }}>
        {!mapReady && (
          <div className="absolute inset-0 bg-gray-100 flex items-center justify-center">
            <p className="text-xs text-rs-text-muted">Loading map…</p>
          </div>
        )}
        <div ref={containerRef} style={{ height: '100%', width: '100%' }} />
        {isDrawing && (
          <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10 px-3 py-1.5 rounded-full bg-rs-navy text-white text-xs font-semibold shadow-lg">
            Click and drag to draw AOI
          </div>
        )}
      </div>

      {/* Leaflet CSS loaded inline */}
      <link
        rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      />
    </div>
  );
}
