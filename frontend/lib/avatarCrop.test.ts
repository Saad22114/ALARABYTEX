import { describe, expect, it } from 'vitest';
import {
  MAX_ZOOM,
  MIN_ZOOM,
  centerView,
  clampOffset,
  clampView,
  clampZoom,
  coverScale,
  cropRegionFromView,
  renderedSize,
} from './avatarCrop';

const STAGE = 280;

describe('clampZoom', () => {
  it('clamps to range', () => {
    expect(clampZoom(0.2)).toBe(MIN_ZOOM);
    expect(clampZoom(9)).toBe(MAX_ZOOM);
    expect(clampZoom(2.5)).toBe(2.5);
  });

  it('falls back for non-finite input', () => {
    // NaN has no meaningful zoom -> fall back to the minimum
    expect(clampZoom(NaN)).toBe(MIN_ZOOM);
    // Infinity is "as far as allowed", so it clamps to the maximum
    expect(clampZoom(Infinity)).toBe(MAX_ZOOM);
    expect(clampZoom(-Infinity)).toBe(MIN_ZOOM);
  });
});

describe('coverScale', () => {
  it('uses the larger of the two ratios so the image covers the square', () => {
    // landscape 200x100 -> stage/height wins
    expect(coverScale(100, 200, 100)).toBe(1);
    // portrait 100x200 -> stage/width wins
    expect(coverScale(100, 100, 200)).toBe(1);
    // 300x300 in a 280 stage
    expect(coverScale(280, 300, 300)).toBeCloseTo(280 / 300, 6);
  });

  it('returns 1 for degenerate input instead of Infinity/NaN', () => {
    expect(coverScale(0, 100, 100)).toBe(1);
    expect(coverScale(100, 0, 100)).toBe(1);
  });
});

describe('renderedSize', () => {
  it('scales both axes by the same factor (no distortion)', () => {
    const a = renderedSize(100, 200, 100, 1);
    const b = renderedSize(100, 200, 100, 1);
    expect(a.width / a.height).toBeCloseTo(b.width / b.height, 9);
    expect(a.width / a.height).toBeCloseTo(2, 6);
  });

  it('never renders smaller than the stage at zoom 1', () => {
    const { width, height } = renderedSize(280, 4000, 100, MIN_ZOOM);
    expect(width).toBeGreaterThanOrEqual(280);
    expect(height).toBeGreaterThanOrEqual(280);
  });

  it('grows with zoom', () => {
    const small = renderedSize(280, 800, 600, 1);
    const large = renderedSize(280, 800, 600, 3);
    expect(large.width).toBeGreaterThan(small.width);
    expect(large.height).toBeGreaterThan(small.height);
  });
});

describe('clampOffset', () => {
  it('keeps the image covering the stage', () => {
    // rendered 400 wide in a 280 stage -> offset in [-120, 0]
    expect(clampOffset(50, 400, 280)).toBe(0);
    expect(clampOffset(-500, 400, 280)).toBe(-120);
    expect(clampOffset(-40, 400, 280)).toBe(-40);
  });

  it('is a no-op for degenerate input', () => {
    expect(clampOffset(10, 0, 280)).toBe(0);
    expect(clampOffset(10, 400, 0)).toBe(0);
  });
});

describe('centerView', () => {
  it('centers the image inside the stage', () => {
    const v = centerView(280, 800, 600);
    const { width, height } = renderedSize(280, 800, 600, v.zoom);
    // the stage centre should coincide with the image centre
    expect(v.offsetX + width / 2).toBeCloseTo(140, 6);
    expect(v.offsetY + height / 2).toBeCloseTo(140, 6);
  });
});

describe('clampView', () => {
  it('pulls an out-of-bounds offset back inside the stage', () => {
    const clamped = clampView({
      stage: STAGE,
      imageWidth: 800,
      imageHeight: 600,
      zoom: 1,
      offsetX: -99999,
      offsetY: 99999,
    });
    const { width, height } = renderedSize(STAGE, 800, 600, 1);
    expect(clamped.offsetX).toBeCloseTo(STAGE - width, 6);
    expect(clamped.offsetY).toBeCloseTo(0, 6);
  });
});

describe('cropRegionFromView', () => {
  it('produces a normalized square region within [0,1]', () => {
    const view = centerView(280, 800, 600);
    const r = cropRegionFromView(view);
    expect(r.x).toBeGreaterThanOrEqual(0);
    expect(r.y).toBeGreaterThanOrEqual(0);
    expect(r.x + r.w).toBeLessThanOrEqual(1 + 1e-9);
    expect(r.y + r.h).toBeLessThanOrEqual(1 + 1e-9);
    // the crop is a square in source pixels
    expect(r.w * 800).toBeCloseTo(r.h * 600, 6);
  });

  it('crops a smaller region as zoom increases', () => {
    const base = cropRegionFromView(centerView(280, 800, 600, 1));
    const zoomed = cropRegionFromView(centerView(280, 800, 600, 3));
    expect(zoomed.w).toBeLessThan(base.w);
    expect(zoomed.h).toBeLessThan(base.h);
  });

  it('reads the left edge correctly when panned to the far end', () => {
    // 800x400 in a 280 stage: cover scale = 280/400 = 0.7 -> width 560
    const { width } = renderedSize(280, 800, 400, 1);
    const minOffset = 280 - width; // fully panned right -> shows the image's left edge
    const r = cropRegionFromView({
      stage: 280,
      imageWidth: 800,
      imageHeight: 400,
      zoom: 1,
      offsetX: minOffset,
      offsetY: 0,
    });
    // offsetX is negative, so -offsetX/width = 280/560 = 0.5:
    // the square stage shows the middle half of a 2:1 image.
    expect(r.x).toBeCloseTo(0.5, 6);
    expect(r.x + r.w).toBeCloseTo(1, 6);
  });

  it('shows the true image edges once zoom exceeds the aspect ratio', () => {
    // At zoom 2 the 800x400 image renders 1120x560, so the stage can be
    // panned all the way to either real edge of the source image.
    const atRightEdge = clampView({
      stage: 280,
      imageWidth: 800,
      imageHeight: 400,
      zoom: 2,
      offsetX: 0, // the stage's left edge sits at image x=0 -> we see the LEFT edge
      offsetY: 0,
    });
    const r = cropRegionFromView(atRightEdge);
    // offsetX = 0 means the stage starts at the image's left edge
    expect(r.x).toBeCloseTo(0, 6);
    expect(r.w).toBeLessThan(1); // a slice, not the whole image

    // Panning the other way reaches the true right edge: x + w == 1
    const atLeftEdge = clampView({
      stage: 280,
      imageWidth: 800,
      imageHeight: 400,
      zoom: 2,
      offsetX: -99999, // clamped to the far end
      offsetY: 0,
    });
    const r2 = cropRegionFromView(atLeftEdge);
    expect(r2.x + r2.w).toBeCloseTo(1, 6);
  });

  it('stays normalized even from a nonsense view', () => {
    const r = cropRegionFromView({
      stage: STAGE,
      imageWidth: 800,
      imageHeight: 600,
      zoom: 99,
      offsetX: NaN,
      offsetY: NaN,
    });
    expect(Number.isFinite(r.x)).toBe(true);
    expect(r.x).toBeGreaterThanOrEqual(0);
    expect(r.x).toBeLessThanOrEqual(1);
  });
});
