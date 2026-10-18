import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: '/forecast',
  },
  {
    path: 'forecast',
    loadComponent: () =>
      import('./features/forecast/forecast.component').then((m) => m.ForecastComponent),
  },
  {
    path: 'segments',
    loadComponent: () =>
      import('./features/segments/segments.component').then((m) => m.SegmentsComponent),
  },
  {
    path: 'pricing',
    loadComponent: () =>
      import('./features/pricing/pricing.component').then((m) => m.PricingComponent),
  },
  {
    path: '**',
    redirectTo: '/forecast',
  },
];
