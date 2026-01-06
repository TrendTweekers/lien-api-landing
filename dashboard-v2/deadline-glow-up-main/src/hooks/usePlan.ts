import { useState, useEffect } from "react";

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

export const usePlan = () => {
  const [planInfo, setPlanInfo] = useState<PlanInfo>({
    plan: "free",
    remainingCalculations: Infinity,
    zapierConnected: false,
    isAdmin: false,
    isSimulated: false,
  });
  const [loading, setLoading] = useState(true);

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

        // Check for admin simulator overrides
        let simulatedPlan: PlanType | null = null;
        let simulatedRemaining: number | null = null;
        let simulatedZapier: boolean | null = null;
        let isSimulated = false;

        if (isAdmin) {
          try {
            const simData = localStorage.getItem('admin_billing_sim');
            if (simData) {
              const parsed = JSON.parse(simData);
              if (parsed.simulated_plan) {
                simulatedPlan = parsed.simulated_plan;
                simulatedRemaining = parsed.simulated_remaining_calculations ?? null;
                simulatedZapier = parsed.simulated_zapier_connected ?? null;
                isSimulated = true;
              }
            }
          } catch (e) {
            console.error('Error parsing admin simulator data:', e);
          }
        }

        const res = await fetch('/api/user/stats', { headers });
        if (!res.ok) {
          // Default to free plan if API fails
        setPlanInfo({
          plan: simulatedPlan || "free",
          remainingCalculations: simulatedRemaining ?? (simulatedPlan ? Infinity : 3),
          zapierConnected: simulatedZapier ?? false,
          isAdmin,
          isSimulated,
          manualCalcUsed: 0,
          manualCalcLimit: simulatedPlan === "free" ? 3 : null,
          manualCalcRemaining: simulatedRemaining ?? 3,
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
        
        // Apply admin simulator overrides if active
        const finalPlan: PlanType = simulatedPlan || (data.plan || data.subscriptionStatus || "free");
        const finalRemaining = simulatedRemaining !== null 
          ? simulatedRemaining 
          : (data.manual_calc_remaining ?? data.calculationsRemaining ?? (data.manual_calc_limit ? data.manual_calc_limit - (data.manual_calc_used || 0) : Infinity));
        const finalZapier = simulatedZapier !== null 
          ? simulatedZapier 
          : (data.zapier_connected === true);

        setPlanInfo({
          plan: finalPlan,
          remainingCalculations: finalRemaining ?? Infinity,
          zapierConnected: finalZapier,
          isAdmin: data.is_admin === true || isAdmin,
          isSimulated,
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
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'admin_billing_sim') {
        fetchPlanInfo();
      }
    };
    window.addEventListener('storage', handleStorageChange);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  return { planInfo, loading };
};

