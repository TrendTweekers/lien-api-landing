import { CheckCircle, CreditCard, Activity } from "lucide-react";

export const AccountOverview = () => {
  return (
    <div className="bg-card rounded-xl p-6 border border-border card-shadow">
      <h2 className="text-lg font-semibold text-foreground mb-6">Account Overview</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
            <CreditCard className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Plan</p>
            <p className="text-2xl font-bold text-foreground">$299<span className="text-base font-normal text-muted-foreground">/month</span></p>
            <p className="text-xs text-muted-foreground mt-0.5">Unlimited API calls</p>
          </div>
        </div>

        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center shrink-0">
            <CheckCircle className="h-5 w-5 text-success" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Status</p>
            <p className="text-2xl font-bold text-success">Active</p>
            <p className="text-xs text-muted-foreground mt-0.5">Next billing: Dec 23, 2025</p>
          </div>
        </div>

        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-info/10 flex items-center justify-center shrink-0">
            <Activity className="h-5 w-5 text-info" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">API Calls This Month</p>
            <p className="text-2xl font-bold text-foreground">1,247</p>
            <p className="text-xs text-muted-foreground mt-0.5">Unlimited plan</p>
          </div>
        </div>
      </div>
    </div>
  );
};
