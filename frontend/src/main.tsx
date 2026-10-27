import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import { App } from './app/App';
import './styles/base.css';
import './styles/portal.css';
import './styles/typography.css';
import './styles/layout.css';
import './styles/buttons.css';
import './styles/images.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode><BrowserRouter basename="/portal"><App /></BrowserRouter></StrictMode>,
);
