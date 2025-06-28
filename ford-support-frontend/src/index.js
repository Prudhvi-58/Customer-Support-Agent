// src/index.js
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
// No need for reportWebVitals or serviceWorker registration here if you deleted them

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
