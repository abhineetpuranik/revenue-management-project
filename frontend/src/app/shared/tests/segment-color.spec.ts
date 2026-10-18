/**
 * Unit tests — getSegmentColor() helper
 */

import { describe, it, expect } from 'vitest';
import { getSegmentColor } from '../segment-color';

describe('getSegmentColor', () => {
  it('returns the expected color for high_value', () => {
    expect(getSegmentColor('high_value')).toBe('var(--color-purple)');
  });

  it('returns the expected color for regular', () => {
    expect(getSegmentColor('regular')).toBe('var(--color-teal)');
  });

  it('returns the expected color for occasional', () => {
    expect(getSegmentColor('occasional')).toBe('var(--color-yellow)');
  });

  it('returns the expected color for at_risk', () => {
    expect(getSegmentColor('at_risk')).toBe('var(--color-coral)');
  });

  it('returns ink (black) as fallback for an unknown label', () => {
    expect(getSegmentColor('vip')).toBe('var(--color-ink)');
  });

  it('returns ink as fallback for an empty string', () => {
    expect(getSegmentColor('')).toBe('var(--color-ink)');
  });

  it('is case-sensitive — mixed case does not match', () => {
    // Labels from the API are always lower_snake_case
    expect(getSegmentColor('High_Value')).toBe('var(--color-ink)');
  });
});
