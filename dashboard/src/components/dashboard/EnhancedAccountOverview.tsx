import { useState, useEffect } from "react";
import { Calculator, FileText, MapPin, TrendingUp, CreditCard, CheckCircle, Zap } from "lucide-react";
import { StatsCard } from "./StatsCard";
import { usePlan } from "@/hooks/usePlan";
import { Button } from "@/components/ui/button";
import { UpgradeModal } from "@/components/UpgradeModal";

export const EnhancedAccountOverview = () => {
  const { planInfo, loading } = usePlan();
  const [totalCalculations, setTotalCalculations] = useState(0);
  const [totalProjects, setTotalProjects] = useState(0);
  const [uniqueStates, setUniqueStates] = useState<string[]>([]);
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('session_token');
    
    // Fetch projects to calculate stats
    fetch("/api/calculations/history", {
      headers: { "Authorization": `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        const projects = Array.isArray(data.history) ? data.history : [];
        
        setTotalCalculations(projects.length);
        setTotalProjects(projects.length);
        
        // Extract unique states from last 30 days
        const thirtyDaysAgo = new Date();
        thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
        
        const recentProjects = projects.filter((p: any) => 
          new Date(p.created_at) > thirtyDaysAgo
        );
        
        const states = Array.from(new Set(
          recentProjects.map((p: any) => p.state).filter(Boolean)
        )) as string[];
        
        setUniqueStates(states);
      })
      .catch(err => console.error('Error fetching stats:', err));
  }, []);

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
      <div className="bg-gradient-to-br from-primary/5 to-primary/10 rounded-xl p-6 border border-border card-shadow">
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
            <div className="w-12 h-12 rounded-xl bg-success/10 flex items-center justify-center shrink-0">
              <CheckCircle className="h-6 w-6 text-success" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground mb-1">Status</p>
              <p className="text-2xl font-bold text-success">Active</p>
              <p className="text-sm text-muted-foreground mt-0.5">
                {planInfo?.resetDate ? `Resets ${new Date(planInfo.resetDate).toLocaleDateString()}` : 'No reset date'}
              </p>
            </div>
          </div>

          {/* API Status (for Automated tier) */}
          {planInfo?.plan === 'automated' && (
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-info/10 flex items-center justify-center shrink-0">
                <Zap className="h-6 w-6 text-info" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground mb-1">API Calls</p>
                <p className="text-2xl font-bold text-foreground">
                  {planInfo?.apiCallsUsed || 0}/{planInfo?.apiCallsLimit || 500}
                </p>
                <p className="text-sm text-muted-foreground mt-0.5">
                  {planInfo?.apiCallsRemaining || 0} remaining
                </p>
              </div>
            </div>
          )}

          {/* Upgrade Button (if not on Automated tier) */}
          {planInfo?.plan !== 'automated' && planInfo?.plan !== 'enterprise' && (
            <Button 
              onClick={() => setUpgradeModalOpen(true)}
              className="bg-primary hover:bg-primary/90 text-primary-foreground font-semibold px-6 py-3 rounded-lg transition-all shadow-lg hover:shadow-xl"
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
          iconColor="text-info"
          iconBg="bg-info/10"
        />
        
        <StatsCard
          title="Active Projects"
          value={totalProjects}
          icon={FileText}
          subtitle="Projects being tracked"
          iconColor="text-success"
          iconBg="bg-success/10"
        />
        
        <StatsCard
          title="States Covered"
          value={uniqueStates.length}
          icon={MapPin}
          subtitle="Last 30 days"
          iconColor="text-primary"
          iconBg="bg-primary/10"
        />
      </div>

      {/* Upgrade Modal */}
      <UpgradeModal open={upgradeModalOpen} onOpenChange={setUpgradeModalOpen} />
    </div>
  );
};

