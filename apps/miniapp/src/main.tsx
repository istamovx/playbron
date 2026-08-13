import '@playbron/ui/styles.css';
import './phone.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './app';
import { initTelegram } from './lib/telegram';

initTelegram();

const container = document.getElementById('root');
if (!container) throw new Error('#root topilmadi');

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
