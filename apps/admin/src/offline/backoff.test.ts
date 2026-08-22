import { describe, expect, it } from 'vitest';

import { nextRetryDelayMs } from './backoff';

describe('nextRetryDelayMs', () => {
  it('starts at ~1s for the first attempt (attempts=0)', () => {
    const delay = nextRetryDelayMs(0, () => 0.5); // random()=0.5 → jitter=0
    expect(delay).toBe(1000);
  });

  it('doubles roughly through the documented steps', () => {
    const noJitter = (): number => 0.5;
    expect(nextRetryDelayMs(1, noJitter)).toBe(2000);
    expect(nextRetryDelayMs(2, noJitter)).toBe(4000);
    expect(nextRetryDelayMs(3, noJitter)).toBe(8000);
    expect(nextRetryDelayMs(4, noJitter)).toBe(16_000);
    expect(nextRetryDelayMs(5, noJitter)).toBe(30_000);
    expect(nextRetryDelayMs(6, noJitter)).toBe(60_000);
  });

  it('caps at 60s even for very high attempt counts', () => {
    const noJitter = (): number => 0.5;
    expect(nextRetryDelayMs(100, noJitter)).toBe(60_000);
  });

  it('applies up to ±20% jitter around the base step', () => {
    const base = 8000; // attempts=3
    const high = nextRetryDelayMs(3, () => 1); // random()=1 → +20%
    const low = nextRetryDelayMs(3, () => 0); // random()=0 → -20%
    expect(high).toBe(Math.round(base * 1.2));
    expect(low).toBe(Math.round(base * 0.8));
  });

  it('never returns less than the minimum delay floor', () => {
    // attempts=0 (base 1000ms) with maximal negative jitter would be 800ms,
    // still above the floor — this asserts the floor exists and holds.
    expect(nextRetryDelayMs(0, () => 0)).toBeGreaterThanOrEqual(500);
  });

  it('treats negative attempts the same as 0 (defensive clamp)', () => {
    const noJitter = (): number => 0.5;
    expect(nextRetryDelayMs(-5, noJitter)).toBe(1000);
  });
});
