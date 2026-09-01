// reportGenerator.ts — Generate a professional PDF analysis report using jsPDF + html2canvas

import jsPDF from 'jspdf';
import type { LiveTraceItem, VisualOutput } from '../types';

interface ImageMeta {
  sensor: string;
  acquisition_date: string;
  resolution_m: number;
  cloud_coverage_pct: number;
  image_type: string;
  cloud_status: string;
}

interface ReportData {
  query: string;
  analysisId: string;
  aoiName?: string;
  images: ImageMeta[];
  traceItems: LiveTraceItem[];
  finalAnswer: string;
  confidence: number;
  confidenceLevel: string;
  evidenceStatus: string;
  evidencePoints: string[];
  visualOutputs: VisualOutput[];
}

// Colours
const NAVY = [22, 43, 75] as const;
const TEAL = [26, 107, 107] as const;
const ORANGE = [224, 123, 57] as const;
const LIGHT_GRAY = [248, 249, 250] as const;
const MID_GRAY = [226, 232, 240] as const;
const TEXT_PRIMARY = [30, 41, 59] as const;
const TEXT_MUTED = [100, 116, 139] as const;

type RGB = readonly [number, number, number];

function setFill(doc: jsPDF, rgb: RGB) { doc.setFillColor(rgb[0], rgb[1], rgb[2]); }
function setDraw(doc: jsPDF, rgb: RGB) { doc.setDrawColor(rgb[0], rgb[1], rgb[2]); }
function setTxt(doc: jsPDF, rgb: RGB)  { doc.setTextColor(rgb[0], rgb[1], rgb[2]); }

function confColor(confidence: number): RGB {
  return confidence >= 0.75 ? [22, 163, 74] : confidence >= 0.5 ? [217, 119, 6] : [220, 38, 38];
}

export async function generateAnalysisReport(data: ReportData): Promise<void> {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const W = 210;
  let y = 0;

  // ─── HEADER ───────────────────────────────────────────────────────────────
  setFill(doc, NAVY);
  doc.rect(0, 0, W, 36, 'F');

  setTxt(doc, [255, 255, 255]);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(18);
  doc.text('SatQuery AI', 14, 16);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  setTxt(doc, [148, 163, 184]);
  doc.text('Vision-Language Agent for Multimodal Remote Sensing', 14, 23);

  // Right: analysis ID + date
  const now = new Date().toLocaleString();
  doc.setFontSize(8);
  doc.text(`Analysis ID: ${data.analysisId.slice(0, 12)}`, W - 14, 14, { align: 'right' });
  doc.text(`Generated: ${now}`, W - 14, 20, { align: 'right' });

  // Teal accent bar
  setFill(doc, TEAL);
  doc.rect(0, 36, W, 2, 'F');

  y = 46;

  // ─── USER QUERY ──────────────────────────────────────────────────────────
  setFill(doc, LIGHT_GRAY);
  doc.roundedRect(14, y, W - 28, 22, 2, 2, 'F');
  setTxt(doc, TEXT_MUTED);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(7);
  doc.text('USER QUERY', 20, y + 7);
  setTxt(doc, TEXT_PRIMARY);
  doc.setFont('helvetica', 'italic');
  doc.setFontSize(10);
  const queryLines = doc.splitTextToSize(`"${data.query}"`, W - 40);
  doc.text(queryLines, 20, y + 13);
  y += 28;

  // AOI
  if (data.aoiName) {
    setTxt(doc, TEAL as unknown as [number,number,number]);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(8);
    doc.text(`📍  Area of Interest: ${data.aoiName}`, 14, y);
    y += 8;
  }

  // ─── TWO-COLUMN: Images | Tools ──────────────────────────────────────────
  const COL1_X = 14;
  const COL2_X = 110;
  const COL_W  = 88;

  // Section headers
  const sectionHeader = (label: string, x: number, yy: number) => {
    setFill(doc, NAVY);
    doc.rect(x, yy, COL_W, 6, 'F');
    setTxt(doc, [255, 255, 255]);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(7);
    doc.text(label, x + 3, yy + 4.2);
    return yy + 8;
  };

  const colY1 = sectionHeader('INPUT IMAGERY', COL1_X, y);
  const colY2 = sectionHeader('TOOLS EXECUTED', COL2_X, y);
  let cy1 = colY1;
  let cy2 = colY2;

  // Images table
  data.images.forEach(img => {
    setFill(doc, img.image_type === 'SAR' ? [22, 43, 75] as RGB : TEAL);
    doc.roundedRect(COL1_X, cy1, 14, 5, 1, 1, 'F');
    setTxt(doc, [255, 255, 255]);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(6);
    doc.text(img.image_type, COL1_X + 7, cy1 + 3.5, { align: 'center' });

    setTxt(doc, TEXT_PRIMARY);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(8);
    doc.text(img.sensor, COL1_X + 17, cy1 + 3.5);
    setTxt(doc, TEXT_MUTED);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7);
    doc.text(`${img.acquisition_date}  ·  ${img.resolution_m}m  ·  Cloud ${img.cloud_coverage_pct}%  ·  ${img.cloud_status}`,
      COL1_X + 17, cy1 + 7.5);

    setFill(doc, MID_GRAY);
    doc.rect(COL1_X, cy1 + 10, COL_W, 0.3, 'F');
    cy1 += 12;
  });

  // Tools table
  data.traceItems.forEach(item => {
    const statusColor: RGB = item.status === 'success' ? [22, 163, 74]
      : item.status === 'warning' ? [217, 119, 6] : [148, 163, 184];

    setFill(doc, statusColor);
    doc.circle(COL2_X + 2.5, cy2 + 3, 2, 'F');

    setTxt(doc, TEXT_PRIMARY);
    doc.setFont('helvetica', item.is_auto_inserted ? 'bold' : 'normal');
    doc.setFontSize(8);
    doc.text(item.step_name + (item.is_auto_inserted ? ' ⚡' : ''), COL2_X + 7, cy2 + 4);

    if (item.confidence && item.confidence > 0) {
      // Mini confidence bar
      const barW = COL_W - 25;
      setFill(doc, MID_GRAY);
      doc.roundedRect(COL2_X + 7, cy2 + 5.5, barW, 1.5, 0.5, 0.5, 'F');
      setFill(doc, statusColor);
      doc.roundedRect(COL2_X + 7, cy2 + 5.5, barW * item.confidence, 1.5, 0.5, 0.5, 'F');
      setTxt(doc, TEXT_MUTED);
      doc.setFontSize(6);
      doc.text(`${(item.confidence * 100).toFixed(0)}%`, COL2_X + COL_W - 4, cy2 + 6.8, { align: 'right' });
    }

    setFill(doc, MID_GRAY);
    doc.rect(COL2_X, cy2 + 9, COL_W, 0.3, 'F');
    cy2 += 11;
  });

  y = Math.max(cy1, cy2) + 6;

  // ─── RESULT ──────────────────────────────────────────────────────────────
  y = sectionHeader('ANALYSIS RESULT', COL1_X, y) - 2;

  setFill(doc, LIGHT_GRAY);
  doc.roundedRect(COL1_X, y, W - 28, 28, 2, 2, 'F');

  // Answer text
  setTxt(doc, TEXT_PRIMARY);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  const ansLines = doc.splitTextToSize(data.finalAnswer, W - 50);
  doc.text(ansLines, 20, y + 7);

  // Confidence box
  const cColor = confColor(data.confidence);
  setFill(doc, cColor);
  doc.roundedRect(W - 55, y + 4, 28, 18, 2, 2, 'F');
  setTxt(doc, [255, 255, 255]);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.text(`${(data.confidence * 100).toFixed(0)}%`, W - 41, y + 14, { align: 'center' });
  doc.setFontSize(6);
  doc.text(data.confidenceLevel.toUpperCase(), W - 41, y + 19, { align: 'center' });

  y += 34;

  // ─── EVIDENCE ────────────────────────────────────────────────────────────
  y = sectionHeader('EVIDENCE & CROSS-MODAL AGREEMENT', COL1_X, y) - 2;

  // Status badge
  const evColor: RGB = data.evidenceStatus === 'consistent' ? [22, 163, 74] : [217, 119, 6];
  setFill(doc, evColor);
  doc.roundedRect(COL1_X, y, 50, 6, 1.5, 1.5, 'F');
  setTxt(doc, [255, 255, 255]);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(7);
  doc.text(
    data.evidenceStatus === 'consistent' ? '✓  CONSISTENT — Tools agree' : '⚠  CONFLICTING — Review needed',
    COL1_X + 25, y + 4, { align: 'center' }
  );

  y += 9;
  data.evidencePoints.forEach(p => {
    setTxt(doc, TEXT_MUTED);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.text(`• ${p}`, COL1_X + 4, y);
    y += 5;
  });
  y += 4;

  // ─── CHANGE MAP (if available) ────────────────────────────────────────────
  const changeMap = data.visualOutputs.find(v => v.type === 'change_map');
  if (changeMap) {
    // Add page if not enough space
    if (y > 230) { doc.addPage(); y = 20; }
    y = sectionHeader('CHANGE MAP', COL1_X, y) - 2;
    try {
      doc.addImage(
        `data:image/png;base64,${changeMap.b64}`,
        'PNG', COL1_X, y, 80, 60
      );
      y += 66;
    } catch { /* image may fail in some environments */ }
  }

  // ─── PROCESSING TRACE ────────────────────────────────────────────────────
  if (y > 240) { doc.addPage(); y = 20; }
  y = sectionHeader('EXECUTION TRACE', COL1_X, y) - 2;

  setFill(doc, [10, 18, 30] as RGB);
  doc.rect(COL1_X, y, W - 28, data.traceItems.length * 5 + 8, 'F');
  setTxt(doc, [100, 200, 180] as RGB);
  doc.setFont('courier', 'normal');
  doc.setFontSize(7);
  data.traceItems.forEach((item, i) => {
    const icon = item.status === 'success' ? '✓' : item.status === 'warning' ? '⚠' : '○';
    const line = `  ${icon} ${item.step_name.padEnd(30)} conf: ${item.confidence ? (item.confidence * 100).toFixed(0) + '%' : 'N/A'}   ${item.execution_time_ms || 0}ms${item.is_auto_inserted ? '  [AUTO-INSERTED]' : ''}`;
    setTxt(doc, item.status === 'success' ? [74, 222, 128] as RGB : item.is_auto_inserted ? ORANGE : [148, 163, 184]);
    doc.text(line, COL1_X + 2, y + 5 + i * 5);
  });
  y += data.traceItems.length * 5 + 14;

  // ─── FOOTER ───────────────────────────────────────────────────────────────
  const pages = doc.getNumberOfPages();
  for (let i = 1; i <= pages; i++) {
    doc.setPage(i);
    setFill(doc, NAVY);
    doc.rect(0, 285, W, 12, 'F');
    setTxt(doc, [148, 163, 184]);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7);
    doc.text('SatQuery AI — Prototype v1.0  ·  All results are simulated (DEMO MODE). Not measured scientific results.', W / 2, 291, { align: 'center' });
    doc.text(`Page ${i} / ${pages}`, W - 14, 291, { align: 'right' });
  }

  // Save
  const fileName = `SatQuery_Analysis_${data.analysisId.slice(0, 8)}_${Date.now()}.pdf`;
  doc.save(fileName);
}
