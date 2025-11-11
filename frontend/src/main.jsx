import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './App.css';
import { AuthProvider } from './context/AuthContext';   // ✅ Auth Context
import ErrorBoundary from './components/ErrorBoundary'; // ✅ ErrorBoundary

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>               {/* Protects the whole app */}
      <AuthProvider>              {/* Provides authentication context */}
        <App />                   {/* main application */}
      </AuthProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
