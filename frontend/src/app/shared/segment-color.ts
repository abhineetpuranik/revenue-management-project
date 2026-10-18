/**
 * Segment color mapping — consistent color per segment label.
 * Falls back to ink for unknown labels (never crashes).
 */

import type { SegmentLabel } from '../core/models/api.models';

const SEGMENT_COLORS: Record<SegmentLabel, string> = {
  high_value: 'var(--color-purple)',
  regular: 'var(--color-teal)',
  occasional: 'var(--color-yellow)',
  at_risk: 'var(--color-coral)',
};

/**
 * Returns a CSS color value for the given segment label.
 * Unknown labels return ink (black) as a safe fallback.
 */
export function getSegmentColor(label: string): string {
  return SEGMENT_COLORS[label as SegmentLabel] ?? 'var(--color-ink)';
}
