import { CheckCircle, CreditCard, Activity, AlertCircle } from "lucide-react";
import { useEffect, useState } from "react";

export const AccountOverview = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({
    planPrice: "--",
    planInterval: "month",
    status: "Loading...",
    nextBilling: "--",
    apiCalls: 0,
    isUnlimited: false
  });

  useEffect(() => {
    const fetchAccountData = async () => {
      try {
        const token = localStorage.getItem('session_token');
        if (!token) {
          setLoading(false);
          return;
        }

        const headers = { 'Authorization': `Bearer ${token}` };

        // Parallel fetch for better performance
        const [sessionRes, statsRes] = await Promise.all([
          fetch('/api/verify-session', { headers }),
          fetch('/api/customer/stats', { headers })
        ]);

        if (sessionRes.ok) {
          const sessionData = await sessionRes.json();
          let apiCalls = 0;

          if (statsRes.ok) {
            const statsData = await statsRes.json();
            apiCalls = statsData.api_calls || 0;
          }

          // Determine status style and text
          const statusRaw = sessionData.subscription_status || 'inactive';
          const statusFormatted = statusRaw.charAt(0).toUpperCase() + statusRaw.slice(1);
          
          // Determine next billing text (mocked for now as not in API)
          const now = new Date();
          const nextBillingText = statusRaw === 'active' 
            ? `Auto-renews ${new Date(now.getFullYear(), now.getMonth() + 1, 1).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}` 
            : 'No active subscription';

          setData({
            planPrice: statusRaw === 'active' ? "299" : "0",
            planInterval: statusRaw === 'active' ? "month" : "month",
            status: statusFormatted,
            nextBilling: nextBillingText,
            apiCalls: apiCalls,
            isUnlimited: statusRaw === 'active'
          });
        }
      } catch (error) {
        console.error("Error fetching account overview:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchAccountData();
  }, []);

  if (loading) {
    return (
      <div className="bg-card rounded-xl p-6 border border-border card-shadow animate-pulse">
        <h2 className="text-lg font-semibold text-foreground mb-6">Account Overview</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-gray-200 dark:bg-gray-700"></div>
              <div className="space-y-2 flex-1">
                <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
                <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-2/3"></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'active') return 'text-success';
    if (s === 'past_due') return 'text-warning';
    if (s === 'cancelled') return 'text-destructive';
    return 'text-muted-foreground';
  };

  const getStatusBg = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'active') return 'bg-success/10';
    if (s === 'past_due') return 'bg-warning/10';
    if (s === 'cancelled') return 'bg-destructive/10';
    return 'bg-muted/10';
  };

  return (
    <div className="bg-card rounded-xl p-6 border border-border card-shadow">
      <h2 className="text-lg font-semibold text-foreground mb-6">Account Overview</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Plan Card */}
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
            <CreditCard className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Plan</p>
            <p className="text-2xl font-bold text-foreground">
              ${data.planPrice}
              <span className="text-base font-normal text-muted-foreground">/{data.planInterval}</span>
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {data.isUnlimited ? "Unlimited API calls" : "Limited access"}
            </p>
          </div>
        </div>

        {/* Status Card */}
        <div className="flex items-start gap-4">
          <div className={`w-10 h-10 rounded-lg ${getStatusBg(data.status)} flex items-center justify-center shrink-0`}>
            {data.status.toLowerCase() === 'active' ? (
              <CheckCircle className={`h-5 w-5 ${getStatusColor(data.status)}`} />
            ) : (
              <AlertCircle className={`h-5 w-5 ${getStatusColor(data.status)}`} />
            )}
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Status</p>
            <p className={`text-2xl font-bold ${getStatusColor(data.status)}`}>{data.status}</p>
            <p className="text-xs text-muted-foreground mt-0.5">Next billing: {data.nextBilling}</p>
          </div>
        </div>

        {/* Usage Card */}
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-info/10 flex items-center justify-center shrink-0">
            <Activity className="h-5 w-5 text-info" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">API Calls This Month</p>
            <p className="text-2xl font-bold text-foreground">{data.apiCalls.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {data.isUnlimited ? "Unlimited plan" : "Upgrade for unlimited"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
