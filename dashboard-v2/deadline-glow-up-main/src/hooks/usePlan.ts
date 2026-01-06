import { useState, useEffect, useMemo } from "react";

export type PlanType = "free" | "basic" | "automated" | "enterprise";

export interface PlanInfo {
  plan: PlanType;
  remainingCalculations: number;
  zapierConnected: boolean;
  isAdmin: boolean;
  isSimulated: boolean;
  // Full stats from /api/user/stats
  manualCalcUsed?: number;
  manualCalcLimit?: number | null;
  manualCalcRemaining?: number | null;
  apiCallsUsed?: number;
  apiCallsLimit?: number | null;
  apiCallsRemaining?: number | null;
  resetDate?: string | null;
  lastSyncAt?: Date | null;
  alertEmail?: string | null;
  emailAlertsEnabled?: boolean;
}

const ADMIN_EMAIL = "admin@stackedboost.com";

// Helper to get admin simulator data from localStorage
function getAdminSim() {
  try {
    const data = localStorage.getItem('admin_billing_sim');
    if (!data) return null;
    const parsed = JSON.parse(data);
    // Support both old and new format
    if (parsed.active || parsed.simulated_plan || parsed.plan) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

export const usePlan = () => {
  const [planInfo, setPlanInfo] = useState<PlanInfo>({
    plan: "free",
    remainingCalculations: Infinity,
    zapierConnected: false,
    isAdmin: false,
    isSimulated: false,
  });
  const [loading, setLoading] = useState(true);
  const [adminSim, setAdminSim] = useState(getAdminSim());

  useEffect(() => {
    const fetchPlanInfo = async () => {
      try {
        const token = localStorage.getItem('session_token');
        if (!token) {
          setLoading(false);
          return;
        }

        // Fetch real stats from API first to get email
        const headers: HeadersInit = {
          "Authorization": `Bearer ${token}`
        };
        
        // Check if user is admin (case-insensitive)
        // Try to get email from session API if not in localStorage
        let userEmail = localStorage.getItem('user_email') || localStorage.getItem('userEmail') || '';
        
        // If email not in localStorage, try fetching from session
        if (!userEmail) {
          try {
            const sessionRes = await fetch('/api/verify-session', { headers });
            if (sessionRes.ok) {
              const sessionData = await sessionRes.json();
              userEmail = sessionData.email || sessionData.user_email || '';
              if (userEmail) {
                localStorage.setItem('user_email', userEmail);
              }
            }
          } catch (e) {
            // Ignore errors, will default to non-admin
          }
        }
        
        const isAdmin = userEmail.toLowerCase().trim() === ADMIN_EMAIL.toLowerCase();
        
        // Update adminSim state if admin
        if (isAdmin) {
          setAdminSim(getAdminSim());
        }

        const res = await fetch('/api/user/stats', { headers });
        if (!res.ok) {
          // Default to free plan if API fails
          setPlanInfo({
            plan: "free",
            remainingCalculations: 3,
            zapierConnected: false,
            isAdmin,
            isSimulated: false,
            manualCalcUsed: 0,
            manualCalcLimit: 3,
            manualCalcRemaining: 3,
            apiCallsUsed: 0,
            apiCallsLimit: null,
            apiCallsRemaining: null,
            resetDate: null,
            lastSyncAt: null,
            alertEmail: null,
            emailAlertsEnabled: true,
          });
          setLoading(false);
          return;
        }

        const data = await res.json();

        setPlanInfo({
          plan: (data.plan || data.subscriptionStatus || "free") as PlanType,
          remainingCalculations: data.manual_calc_remaining ?? data.calculationsRemaining ?? (data.manual_calc_limit ? data.manual_calc_limit - (data.manual_calc_used || 0) : Infinity),
          zapierConnected: data.zapier_connected === true,
          isAdmin: data.is_admin === true || isAdmin,
          isSimulated: false,
          manualCalcUsed: data.manual_calc_used ?? 0,
          manualCalcLimit: data.manual_calc_limit ?? null,
          manualCalcRemaining: data.manual_calc_remaining ?? null,
          apiCallsUsed: data.api_calls_used ?? 0,
          apiCallsLimit: data.api_calls_limit ?? null,
          apiCallsRemaining: data.api_calls_remaining ?? null,
          resetDate: data.next_reset ?? null,
          lastSyncAt: new Date(),
          alertEmail: data.alert_email ?? null,
          emailAlertsEnabled: data.email_alerts_enabled ?? true,
        });
      } catch (error) {
        console.error('Error fetching plan info:', error);
        setPlanInfo({
          plan: "free",
          remainingCalculations: 3,
          zapierConnected: false,
          isAdmin: false,
          isSimulated: false,
          manualCalcUsed: 0,
          manualCalcLimit: 3,
          manualCalcRemaining: 3,
          apiCallsUsed: 0,
          apiCallsLimit: null,
          apiCallsRemaining: null,
          resetDate: null,
          lastSyncAt: null,
          alertEmail: null,
          emailAlertsEnabled: true,
        });
      } finally {
        setLoading(false);
      }
    };

    fetchPlanInfo();

    // Listen for simulator changes
    const handleSimUpdate = () => {
      setAdminSim(getAdminSim());
      // Refetch plan info to get latest backend data, then merge
      fetchPlanInfo();
    };
    
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'admin_billing_sim') {
        handleSimUpdate();
      }
    };
    
    window.addEventListener('admin-billing-sim-updated', handleSimUpdate);
    window.addEventListener('storage', handleStorageChange);

    return () => {
      window.removeEventListener('admin-billing-sim-updated', handleSimUpdate);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  // Merge simulator overrides with backend plan info
  const effectivePlanInfo = useMemo(() => {
    if (!planInfo) return planInfo;
    
    // Only apply simulator if admin and simulator is active
    const userEmail = localStorage.getItem('user_email') || localStorage.getItem('userEmail') || '';
    const isAdmin = userEmail.toLowerCase().trim() === ADMIN_EMAIL.toLowerCase();
    
    // Check if simulator is active (support both old and new format)
    const simActive = adminSim && (adminSim.active === true || adminSim.simulated_plan || adminSim.plan);
    
    if (!isAdmin || !simActive) {
      return planInfo;
    }

    // Merge simulator overrides (support both old and new format)
    return {
      ...planInfo,
      plan: (adminSim.plan || adminSim.simulated_plan) as PlanType,
      remainingCalculations: adminSim.remainingCalculations ?? adminSim.simulated_remaining_calculations ?? planInfo.remainingCalculations,
      zapierConnected: adminSim.zapierConnected ?? adminSim.simulated_zapier_connected ?? planInfo.zapierConnected,
      apiCallsUsed: adminSim.apiCallsUsed ?? adminSim.simulated_api_used ?? planInfo.apiCallsUsed,
      isSimulated: true,
    };
  }, [planInfo, adminSim]);

  return { planInfo: effectivePlanInfo || planInfo, loading, adminSim };
};

