/**
 * Unit tests — LoadingStateComponent and ErrorStateComponent
 */

import { describe, it, expect } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { LoadingStateComponent } from '../components/loading-state.component';
import { ErrorStateComponent } from '../components/error-state.component';
import { EmptyStateComponent } from '../components/empty-state.component';

describe('LoadingStateComponent', () => {
  it('renders the default message', async () => {
    const fixture = TestBed.createComponent(LoadingStateComponent);
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;
    expect(el.textContent).toContain('Loading...');
  });

  it('renders a custom message', async () => {
    const fixture = TestBed.createComponent(LoadingStateComponent);
    fixture.componentRef.setInput('message', 'Fetching products…');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Fetching products…');
  });
});

describe('ErrorStateComponent', () => {
  it('renders the error message', () => {
    const fixture = TestBed.createComponent(ErrorStateComponent);
    fixture.componentRef.setInput('message', 'Something went wrong.');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Something went wrong.');
  });

  it('shows retry button by default', () => {
    const fixture = TestBed.createComponent(ErrorStateComponent);
    fixture.componentRef.setInput('message', 'Oops!');
    fixture.detectChanges();
    const btn = fixture.debugElement.query(By.css('button'));
    expect(btn).not.toBeNull();
  });

  it('hides retry button when showRetry is false', () => {
    const fixture = TestBed.createComponent(ErrorStateComponent);
    fixture.componentRef.setInput('message', 'Oops!');
    fixture.componentRef.setInput('showRetry', false);
    fixture.detectChanges();
    const btn = fixture.debugElement.query(By.css('button'));
    expect(btn).toBeNull();
  });

  it('emits retry event when button is clicked', () => {
    const fixture = TestBed.createComponent(ErrorStateComponent);
    fixture.componentRef.setInput('message', 'Oops!');
    fixture.detectChanges();

    let emitted = false;
    fixture.componentInstance.retry.subscribe(() => (emitted = true));

    const btn: HTMLButtonElement = fixture.debugElement.query(By.css('button')).nativeElement;
    btn.click();
    expect(emitted).toBe(true);
  });
});

describe('EmptyStateComponent', () => {
  it('renders the default message', () => {
    const fixture = TestBed.createComponent(EmptyStateComponent);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No data available.');
  });

  it('renders a custom message', () => {
    const fixture = TestBed.createComponent(EmptyStateComponent);
    fixture.componentRef.setInput('message', 'No products match.');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No products match.');
  });
});
