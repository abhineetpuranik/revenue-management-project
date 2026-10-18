/**
 * Unit tests — ExplanationPanelComponent (all 4 states)
 */

import { describe, it, expect } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { ExplanationPanelComponent } from '../components/explanation-panel.component';

describe('ExplanationPanelComponent', () => {
  function create() {
    const fixture = TestBed.createComponent(ExplanationPanelComponent);
    return { fixture, comp: fixture.componentInstance };
  }

  // ── Loading state ─────────────────────────────────────────────────────

  it('loading state — shows spinner with GENERATING EXPLANATION', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('state', 'loading');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('GENERATING EXPLANATION');
  });

  // ── Available state ───────────────────────────────────────────────────

  it('available state — shows explanation text as plain text', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('state', 'available');
    fixture.componentRef.setInput('text', 'Raise the price of P027 by 7.0%');
    fixture.componentRef.setInput('source', 'fallback');
    fixture.componentRef.setInput('generatedAt', '2026-10-15 08:38:57');
    fixture.detectChanges();
    const body = fixture.debugElement.query(By.css('.explanation-panel__body'));
    expect(body).not.toBeNull();
    expect(body.nativeElement.textContent).toContain('Raise the price of P027 by 7.0%');
  });

  it('available state — shows source badge', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('state', 'available');
    fixture.componentRef.setInput('text', 'test');
    fixture.componentRef.setInput('source', 'llm');
    fixture.detectChanges();
    const badge = fixture.debugElement.query(By.css('.source-badge'));
    expect(badge.nativeElement.textContent.trim()).toBe('llm');
    expect(badge.classes['source-badge--llm']).toBe(true);
  });

  it('available state — shows caption about analytical models', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('state', 'available');
    fixture.componentRef.setInput('text', 'test');
    fixture.detectChanges();
    const caption = fixture.debugElement.query(By.css('.explanation-panel__caption'));
    expect(caption.nativeElement.textContent).toContain('All numbers come from the analytical models');
  });

  // ── Unavailable state ────────────────────────────────────────────────

  it('unavailable state — shows the returned reason', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('state', 'unavailable');
    fixture.componentRef.setInput('reason', 'No explanation has been generated yet.');
    fixture.detectChanges();
    const el = fixture.debugElement.query(By.css('.explanation-panel__unavailable'));
    expect(el).not.toBeNull();
    expect(el.nativeElement.textContent).toContain('No explanation has been generated yet.');
  });

  // ── Error state ───────────────────────────────────────────────────────

  it('error state — shows error message with retry button', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('state', 'error');
    fixture.componentRef.setInput('reason', 'Failed to load explanation.');
    fixture.detectChanges();
    const btn = fixture.debugElement.query(By.css('button'));
    expect(btn).not.toBeNull();
    expect(btn.nativeElement.textContent).toContain('Retry');
  });

  it('error state — emits retry when button clicked', () => {
    const { fixture, comp } = create();
    fixture.componentRef.setInput('state', 'error');
    fixture.componentRef.setInput('reason', 'Failed.');
    fixture.detectChanges();

    let emitted = false;
    comp.retry.subscribe(() => (emitted = true));

    const btn: HTMLButtonElement = fixture.debugElement.query(By.css('button')).nativeElement;
    btn.click();
    expect(emitted).toBe(true);
  });

  // ── Plain text rendering (security) ───────────────────────────────────

  it('renders markup as literal text, never as HTML', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('state', 'available');
    fixture.componentRef.setInput('text', '<b>not bold</b><script>alert(1)</script>');
    fixture.detectChanges();
    const textEl = fixture.debugElement.query(By.css('.explanation-panel__text'));
    // The text should be literally present
    expect(textEl.nativeElement.textContent).toContain('<b>not bold</b>');
    expect(textEl.nativeElement.textContent).toContain('<script>alert(1)</script>');
    // No actual <b> or <script> element should be rendered
    const bold = fixture.nativeElement.querySelector('b');
    const script = fixture.nativeElement.querySelector('script');
    expect(bold).toBeNull();
    expect(script).toBeNull();
  });

  // ── Fallback source badge styling ────────────────────────────────────

  it('fallback source — shows fallback badge class', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('state', 'available');
    fixture.componentRef.setInput('text', 'test');
    fixture.componentRef.setInput('source', 'fallback');
    fixture.detectChanges();
    const badge = fixture.debugElement.query(By.css('.source-badge'));
    expect(badge.classes['source-badge--fallback']).toBe(true);
  });

  it('mock source — shows mock badge class', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('state', 'available');
    fixture.componentRef.setInput('text', 'test');
    fixture.componentRef.setInput('source', 'mock');
    fixture.detectChanges();
    const badge = fixture.debugElement.query(By.css('.source-badge'));
    expect(badge.classes['source-badge--mock']).toBe(true);
  });
});
