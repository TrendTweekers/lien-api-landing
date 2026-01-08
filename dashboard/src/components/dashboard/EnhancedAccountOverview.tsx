import { useState, useMemo } from "react";
import { Calculator, FileText, MapPin, TrendingUp, CreditCard, CheckCircle, Zap } from "lucide-react";
import { StatsCard } from "./StatsCard";
import { usePlan } from "@/hooks/usePlan";
import { Button } from "@/components/ui/button";

interface EnhancedAccountOverviewProps {
  projects?: any[];
}

export const EnhancedAccountOverview = ({ projects = [] }: EnhancedAccountOverviewProps) => {
  const { planInfo, loading } = usePlan();
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);

  // Use props instead of fetching - PERFORMANCE OPTIMIZATION
  const { totalCalculations, totalProjects, uniqueStates } = useMemo(() => {
    const totalCalculations = projects.length;
    const totalProjects = projects.length;
    
    // Extract unique states from last 30 days
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    
    const recentProjects = projects.filter((p: any) => 
      p.created_at && new Date(p.created_at) > thirtyDaysAgo
    );
    
    const states = Array.from(new Set(
      recentProjects.map((p: any) => p.state).filter(Boolean)
    )) as string[];
    
    return { totalCalculations, totalProjects, uniqueStates: states };
  }, [projects]);

  const getPlanDisplayName = (plan: string) => {
    const names: Record<string, string> = {
      'free': 'Free Trial',
      'basic': 'Basic Tracker',
      'automated': 'Automated Compliance',
      'enterprise': 'Enterprise'
    };
    return names[plan] || plan;
  };

  const getPlanPrice = (plan: string) => {
    const prices: Record<string, string> = {
      'free': '$0',
      'basic': '$49',
      'automated': '$149',
      'enterprise': 'Custom'
    };
    return prices[plan] || '$0';
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-32 bg-muted rounded-xl"></div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="h-32 bg-muted rounded-xl"></div>
          <div className="h-32 bg-muted rounded-xl"></div>
          <div className="h-32 bg-muted rounded-xl"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Account Overview Header */}
      <div className="bg-card rounded-xl p-6 border border-border card-shadow">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          {/* Plan Info */}
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center shrink-0">
              <CreditCard className="h-6 w-6 text-primary" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground mb-1">Current Plan</p>
              <p className="text-2xl font-bold text-foreground">
                {getPlanDisplayName(planInfo?.plan || 'free')}
              </p>
              <p className="text-sm text-muted-foreground mt-0.5">
                {getPlanPrice(planInfo?.plan || 'free')}/month
              </p>
            </div>
          </div>

          {/* Status */}
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-green-100 flex items-center justify-center shrink-0">
              <CheckCircle className="h-6 w-6 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground mb-1">Status</p>
              <p className="text-2xl font-bold text-green-600">Active</p>
              <p className="text-sm text-muted-foreground mt-0.5">
                {planInfo?.next_reset ? `Resets ${new Date(planInfo.next_reset).toLocaleDateString()}` : 'No reset date'}
              </p>
            </div>
          </div>

          {/* API Status (for Automated tier) */}
          {planInfo?.plan === 'automated' && (
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center shrink-0">
                <Zap className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground mb-1">API Calls</p>
                <p className="text-2xl font-bold text-foreground">
                  {planInfo?.api_calls_used || 0}/{planInfo?.api_calls_limit || 500}
                </p>
                <p className="text-sm text-muted-foreground mt-0.5">
                  {planInfo?.api_calls_remaining || 0} remaining
                </p>
              </div>
            </div>
          )}

          {/* Upgrade Button (if not on Automated tier) */}
          {planInfo?.plan !== 'automated' && (
            <Button 
              onClick={() => setUpgradeModalOpen(true)}
              className="bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white font-semibold px-6 py-3 rounded-lg transition-all shadow-lg hover:shadow-xl"
            >
              <TrendingUp className="h-4 w-4 mr-2" />
              Upgrade Plan
            </Button>
          )}
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatsCard
          title="Total Calculations"
          value={totalCalculations}
          icon={Calculator}
          subtitle="All time calculations"
          iconColor="text-blue-600"
          iconBg="bg-blue-100"
        />
        
        <StatsCard
          title="Active Projects"
          value={totalProjects}
          icon={FileText}
          subtitle="Projects being tracked"
          iconColor="text-green-600"
          iconBg="bg-green-100"
        />
        
        <StatsCard
          title="States Covered"
          value={uniqueStates.length}
          icon={MapPin}
          subtitle="Last 30 days"
          iconColor="text-purple-600"
          iconBg="bg-purple-100"
        />
      </div>

      {/* Upgrade Modal */}
      {upgradeModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-8 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start mb-6">
              <div>
                <h2 className="text-3xl font-bold text-gray-900 mb-2">Upgrade Your Plan</h2>
                <p className="text-gray-600">Choose the plan that fits your needs</p>
              </div>
              <button
                onClick={() => setUpgradeModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-6">
              {/* Basic Tier */}
              <div className="border-2 border-gray-200 rounded-xl p-6 hover:border-orange-500 transition-all">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-xl font-bold text-gray-900">Basic Tracker</h3>
                    <p className="text-gray-600 text-sm mt-1">For small teams and individual users</p>
                  </div>
                  <div className="text-right">
                    <p className="text-3xl font-bold text-gray-900">$49</p>
                    <p className="text-sm text-gray-500">/month</p>
                  </div>
                </div>
                <ul className="space-y-3 mb-6">
                  <li className="flex items-start gap-3">
                    <CheckCircle className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-700">Unlimited calculations</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-700">Email reminders (7-day & 1-day)</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-700">PDF/CSV export</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-700">Email support</span>
                  </li>
                </ul>
                <Button className="w-full bg-orange-500 hover:bg-orange-600 text-white font-semibold py-3 rounded-lg">
                  Upgrade to Basic
                </Button>
              </div>

              {/* Automated Tier */}
              <div className="border-2 border-orange-500 rounded-xl p-6 bg-gradient-to-br from-orange-50 to-orange-100 relative overflow-hidden">
                <div className="absolute top-4 right-4">
                  <span className="bg-orange-500 text-white text-xs font-bold px-3 py-1 rounded-full">
                    POPULAR
                  </span>
                </div>
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-xl font-bold text-gray-900">Automated Compliance</h3>
                    <p className="text-gray-700 text-sm mt-1">For growing businesses with automation needs</p>
                  </div>
                  <div className="text-right">
                    <p className="text-3xl font-bold text-gray-900">$149</p>
                    <p className="text-sm text-gray-600">/month</p>
                  </div>
                </div>
                <ul className="space-y-3 mb-6">
                  <li className="flex items-start gap-3">
                    <CheckCircle className="h-5 w-5 text-orange-600 shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-700 font-medium">Everything in Basic, plus:</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle className="h-5 w-5 text-orange-600 shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-700">Zapier automation (6,000+ apps)</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle className="h-5 w-5 text-orange-600 shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-700">Multi-channel alerts (Slack/SMS/Calendar)</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle className="h-5 w-5 text-orange-600 shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-700">API access (500 calls/month)</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle className="h-5 w-5 text-orange-600 shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-700">Priority support</span>
                  </li>
                </ul>
                <Button className="w-full bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white font-semibold py-3 rounded-lg shadow-lg">
                  Upgrade to Automated
                </Button>
              </div>
            </div>

            <p className="text-center text-sm text-gray-500 mt-6">
              Plans renew automatically. Cancel anytime.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
