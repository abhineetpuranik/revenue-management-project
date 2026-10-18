/**
 * Unit tests — StatTileComponent
 */

import { describe, it, expect } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { StatTileComponent } from '../components/stat-tile.component';

describe('StatTileComponent', () => {
  it('renders value and label', () => {
    const fixture = TestBed.createComponent(StatTileComponent);
    fixture.componentRef.setInput('value', '9.7%');
    fixture.componentRef.setInput('label', 'MAPE');
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    expect(el.textContent).toContain('9.7%');
    expect(el.textContent).toContain('MAPE');
  });

  it('applies the bgColor as inline style on the tile', () => {
    const fixture = TestBed.createComponent(StatTileComponent);
    fixture.componentRef.setInput('value', '1000');
    fixture.componentRef.setInput('label', 'Customers');
    fixture.componentRef.setInput('bgColor', 'var(--color-lime)');
    fixture.detectChanges();

    const tile = fixture.debugElement.query(By.css('.stat-tile'));
    expect(tile.styles['backgroundColor']).toBe('var(--color-lime)');
  });

  it('defaults bgColor to lime', () => {
    const fixture = TestBed.createComponent(StatTileComponent);
    fixture.componentRef.setInput('value', '1');
    fixture.componentRef.setInput('label', 'X');
    fixture.detectChanges();

    const tile = fixture.debugElement.query(By.css('.stat-tile'));
    expect(tile.styles['backgroundColor']).toBe('var(--color-lime)');
  });

  it('renders numeric value as string', () => {
    const fixture = TestBed.createComponent(StatTileComponent);
    fixture.componentRef.setInput('value', 42);
    fixture.componentRef.setInput('label', 'Count');
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('42');
  });
});
