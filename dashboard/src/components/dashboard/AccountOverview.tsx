import { CheckCircle, CreditCard, Activity, AlertCircle } from "lucide-react";
import { usePlan } from "@/hooks/usePlan";

export const AccountOverview = () => {
  const { planInfo, loading } = usePlan();

  // Format plan display name
  const getPlanDisplayName = (plan: string) => {
    switch (plan) {
      case "free": return "Free Calculator";
      case "basic": return "Basic Tracker";
      case "automated": return "Automated Compliance";
      case "enterprise": return "Enterprise";
      default: return "Free Calculator";
    }
  };

  // Format plan price
  const getPlanPrice = (plan: string) => {
    switch (plan) {
      case "free": return "$0";
      case "basic": return "$49";
      case "automated": return "$149";
      case "enterprise": return "$499";
      default: return "$0";
    }
  };

  // Format reset date
  const formatResetDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return "—";
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch {
      return "—";
    }
  };

  // Get status based on plan
  const getStatus = (plan: string) => {
    if (plan === "free") return "Free";
    return "Active";
  };

  // Get API calls display
  const getApiCallsDisplay = () => {
    if (planInfo.plan === "enterprise") {
      return { used: "Unlimited", limit: null, text: "Unlimited" };
    }
    if (planInfo.plan === "automated") {
      return {
        used: planInfo.apiCallsUsed ?? 0,
        limit: planInfo.apiCallsLimit ?? 500,
        text: `${planInfo.apiCallsUsed ?? 0}/${planInfo.apiCallsLimit ?? 500}`
      };
    }
    return { used: planInfo.apiCallsUsed ?? 0, limit: null, text: "Not included" };
  };

  const apiDisplay = getApiCallsDisplay();

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

  const status = getStatus(planInfo.plan);

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
            <p className="text-xl font-bold text-foreground">
              {getPlanDisplayName(planInfo.plan)}
            </p>
            <p className="text-sm text-muted-foreground mt-0.5">
              {getPlanPrice(planInfo.plan)}/month
            </p>
          </div>
        </div>

        {/* Status Card */}
        <div className="flex items-start gap-4">
          <div className={`w-10 h-10 rounded-lg ${getStatusBg(status)} flex items-center justify-center shrink-0`}>
            {status.toLowerCase() === 'active' ? (
              <CheckCircle className={`h-5 w-5 ${getStatusColor(status)}`} />
            ) : (
              <AlertCircle className={`h-5 w-5 ${getStatusColor(status)}`} />
            )}
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Status</p>
            <p className={`text-2xl font-bold ${getStatusColor(status)}`}>{status}</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Resets: {formatResetDate(planInfo.resetDate)}
            </p>
          </div>
        </div>

        {/* Usage Card */}
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-info/10 flex items-center justify-center shrink-0">
            <Activity className="h-5 w-5 text-info" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">API Calls</p>
            <p className="text-2xl font-bold text-foreground">{apiDisplay.text}</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {planInfo.plan === "enterprise" ? "Unlimited" : planInfo.plan === "automated" ? `${planInfo.apiCallsRemaining ?? 0} remaining` : "Not included"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
