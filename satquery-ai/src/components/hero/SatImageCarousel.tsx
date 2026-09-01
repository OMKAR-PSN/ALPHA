// SatImageCarousel — Auto-rotating 3D CSS carousel of satellite imagery

import { useEffect, useRef, useState } from 'react';

const SLIDES = [
  {
    src: '/images/sat_urban_river.jpg',
    label: 'Urban Expansion',
    sublabel: 'Sentinel-2 · False Colour',
    badge: 'Optical',
    badgeColor: '#1A6B6B',
  },
  {
    src: '/images/sat_change.jpg',
    label: 'Change Detection',
    sublabel: 'Bi-Temporal · 2024–2026',
    badge: 'Change Map',
    badgeColor: '#E07B39',
  },
  {
    src: '/images/sat_sar.jpg',
    label: 'SAR Analysis',
    sublabel: 'Sentinel-1 · C-Band',
    badge: 'SAR',
    badgeColor: '#162B4B',
  },
  {
    src: '/images/sat_cloud.jpg',
    label: 'Cloud Scene',
    sublabel: 'Auto-Reconstruction Ready',
    badge: 'Cloud',
    badgeColor: '#64748b',
  },
];

const N = SLIDES.length;
const ANGLE = 360 / N; // 90° per card
const RADIUS = 220;    // px — distance from center

export default function SatImageCarousel() {
  const [active, setActive] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const start = () => {
    intervalRef.current = setInterval(() => {
      setActive(a => (a + 1) % N);
    }, 2800);
  };

  useEffect(() => {
    start();
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, []);

  const pause = () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  const resume = () => start();

  const rotationY = -active * ANGLE;

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: '480px', height: '360px', perspective: '900px' }}
      onMouseEnter={pause}
      onMouseLeave={resume}
    >
      {/* Ambient glow beneath */}
      <div
        className="absolute bottom-0 left-1/2 -translate-x-1/2 w-64 h-8 rounded-full blur-2xl"
        style={{ background: 'radial-gradient(ellipse, rgba(26,107,107,0.5) 0%, transparent 80%)' }}
      />

      {/* 3D Stage */}
      <div
        style={{
          width: '260px',
          height: '260px',
          position: 'relative',
          transformStyle: 'preserve-3d',
          transition: 'transform 0.85s cubic-bezier(0.25, 0.46, 0.45, 0.94)',
          transform: `rotateY(${rotationY}deg)`,
        }}
      >
        {SLIDES.map((slide, i) => {
          const angle = i * ANGLE;
          const isActive = i === active;
          return (
            <div
              key={slide.src}
              onClick={() => setActive(i)}
              style={{
                position: 'absolute',
                inset: 0,
                transformStyle: 'preserve-3d',
                transform: `rotateY(${angle}deg) translateZ(${RADIUS}px)`,
                transition: 'box-shadow 0.3s',
                cursor: 'pointer',
                borderRadius: '16px',
                overflow: 'hidden',
                boxShadow: isActive
                  ? '0 0 0 2px rgba(26,107,107,0.9), 0 20px 60px rgba(0,0,0,0.5)'
                  : '0 8px 32px rgba(0,0,0,0.4)',
              }}
            >
              {/* Image */}
              <img
                src={slide.src}
                alt={slide.label}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  display: 'block',
                  filter: isActive ? 'brightness(1)' : 'brightness(0.55)',
                  transition: 'filter 0.6s',
                }}
                draggable={false}
              />

              {/* Overlay gradient */}
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  background: 'linear-gradient(to top, rgba(10,18,30,0.85) 0%, transparent 50%)',
                  pointerEvents: 'none',
                }}
              />

              {/* Badge */}
              <div
                style={{
                  position: 'absolute',
                  top: '10px',
                  left: '10px',
                  padding: '3px 8px',
                  borderRadius: '5px',
                  background: slide.badgeColor,
                  color: '#fff',
                  fontSize: '10px',
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  opacity: isActive ? 1 : 0.6,
                  transition: 'opacity 0.4s',
                }}
              >
                {slide.badge}
              </div>

              {/* Caption */}
              <div
                style={{
                  position: 'absolute',
                  bottom: 0,
                  left: 0,
                  right: 0,
                  padding: '10px 12px',
                  opacity: isActive ? 1 : 0,
                  transform: isActive ? 'translateY(0)' : 'translateY(6px)',
                  transition: 'opacity 0.5s, transform 0.5s',
                }}
              >
                <p style={{ color: '#fff', fontSize: '13px', fontWeight: 700, margin: 0, lineHeight: 1.2 }}>
                  {slide.label}
                </p>
                <p style={{ color: 'rgba(255,255,255,0.65)', fontSize: '11px', margin: '2px 0 0', fontFamily: 'monospace' }}>
                  {slide.sublabel}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Dot indicators */}
      <div
        style={{
          position: 'absolute',
          bottom: '-4px',
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          gap: '6px',
        }}
      >
        {SLIDES.map((_, i) => (
          <button
            key={i}
            onClick={() => setActive(i)}
            style={{
              width: i === active ? '20px' : '6px',
              height: '6px',
              borderRadius: '3px',
              border: 'none',
              background: i === active ? '#1A6B6B' : 'rgba(255,255,255,0.3)',
              cursor: 'pointer',
              padding: 0,
              transition: 'all 0.35s cubic-bezier(0.4,0,0.2,1)',
            }}
          />
        ))}
      </div>

      {/* Scan-line overlay for sci-fi feel */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,0,0.04) 3px, rgba(0,0,0,0.04) 4px)',
          pointerEvents: 'none',
          borderRadius: '16px',
        }}
      />
    </div>
  );
}
