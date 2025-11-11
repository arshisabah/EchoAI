import { useState, useEffect, useCallback, useRef } from 'react';
import { healthAPI } from '../services/api';

/**
 * useBackendStatus()
 * 
 * Monitors backend health every intervalMs (default 30s)
 * - Persists last known state in localStorage
 * - Provides manual recheck() function
 * - Returns backendStatus: 'connected' | 'degraded' | 'disconnected' | 'checking'
 */
export const useBackendStatus = (intervalMs = 30000) => {
  const [backendStatus, setBackendStatus] = useState(() => {
    // ✅ Load last known status from localStorage on first render
    return localStorage.getItem('backend_status') || 'checking';
  });

  const intervalRef = useRef(null);

  const checkBackendHealth = useCallback(async () => {
    try {
      const health = await healthAPI.checkHealth();
      const newStatus = health.status === 'healthy' ? 'connected' : 'degraded';
      setBackendStatus(newStatus);
      localStorage.setItem('backend_status', newStatus);
      console.log(`✅ Backend status: ${newStatus}`);
    } catch (error) {
      console.error('❌ Backend health check failed:', error);
      setBackendStatus('disconnected');
      localStorage.setItem('backend_status', 'disconnected');
    }
  }, []);

  useEffect(() => {
    // Run immediately on mount
    checkBackendHealth();

    // Start periodic checks
    intervalRef.current = setInterval(checkBackendHealth, intervalMs);

    // Cleanup on unmount
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [checkBackendHealth, intervalMs]);

  return { backendStatus, checkBackendHealth };
};

export default useBackendStatus;
