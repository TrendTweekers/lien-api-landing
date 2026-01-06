import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Rocket } from "lucide-react";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { AccountOverview } from "@/components/dashboard/AccountOverview";
import { DeadlineCalculator } from "@/components/dashboard/DeadlineCalculator";
import { ProjectsTable } from "@/components/dashboard/ProjectsTable";
import { ApiKeySection } from "@/components/dashboard/ApiKeySection";
import { UsageStats } from "@/components/dashboard/UsageStats";
import { UsageWidget } from "@/components/dashboard/UsageWidget";
import { BillingSection } from "@/components/dashboard/BillingSection";
import { PartnerProgram } from "@/components/dashboard/PartnerProgram";
import { ApiDocs } from "@/components/dashboard/ApiDocs";
import UpgradePrompt from "@/components/UpgradePrompt";
import { ZapierStatusCard } from "@/components/dashboard/ZapierStatusCard";
import { AdminSimulator } from "@/components/AdminSimulator";
import { EmailCaptures } from "@/components/admin/EmailCaptures";
import { usePlan } from "@/hooks/usePlan";

const Index = () => {
  const navigate = useNavigate();
  const { planInfo } = usePlan();
  const [userStats, setUserStats] = useState<{
    calculationsUsed: number;
    calculationsLimit: number | null;
    subscriptionStatus: string;
  } | null>(null);
  const [expandedProjectId, setExpandedProjectId] = useState<number | null>(null);

  useEffect(() => {
    // Check for session token and verify session
    const token = localStorage.getItem('session_token');
    if (!token) {
      window.location.href = '/login.html';
      return;
    }
    
    fetch('/api/verify-session', {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(res => {
      if (!res.ok) {
        window.location.href = '/login.html';
      }
    }).catch(() => {
      window.location.href = '/login.html';
    });

    // Fetch user stats
    fetch('/api/user/stats', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => {
        setUserStats({
          calculationsUsed: data.calculationsUsed || 0,
          calculationsLimit: data.calculationsLimit || null,
          subscriptionStatus: data.subscriptionStatus || 'free'
        });
      })
      .catch(err => {
        console.error('Error fetching user stats:', err);
      });
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <DashboardHeader />
      
      <main className="container py-8">
        <div className="space-y-8">
          {/* Welcome */}
          <div className="animate-fade-in">
            <h1 className="text-3xl font-bold text-foreground mb-2">
              Welcome back, <span className="text-primary">Admin</span>
            </h1>
            <p className="text-muted-foreground">Manage your lien deadlines and integrations from one place.</p>
          </div>

          {/* Upgrade Prompt for Free Tier Users */}
          {userStats && userStats.subscriptionStatus === 'free' && (
            <UpgradePrompt 
              calculationsUsed={userStats.calculationsUsed}
              calculationsLimit={userStats.calculationsLimit || 3}
            />
          )}

          {/* Account Overview */}
          <div className="animate-slide-up" style={{ animationDelay: "0.1s" }}>
            <AccountOverview />
          </div>

          {/* Deadline Calculator */}
          <div className="animate-slide-up" style={{ animationDelay: "0.15s" }}>
            <DeadlineCalculator />
          </div>

          {/* Zapier Automation Card - Status-Driven */}
          <div className="animate-slide-up" style={{ animationDelay: "0.2s" }}>
            <ZapierStatusCard 
              onProjectExpand={(projectId) => {
                setExpandedProjectId(projectId);
                // Scroll to projects table after a brief delay
                setTimeout(() => {
                  const projectsSection = document.querySelector('[data-projects-section]');
                  if (projectsSection) {
                    projectsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  }
                }, 100);
              }}
            />
          </div>

          {/* Projects Table */}
          <div className="animate-slide-up" style={{ animationDelay: "0.25s" }} data-projects-section>
            <ProjectsTable 
              expandedProjectId={expandedProjectId}
              onExpandedProjectChange={setExpandedProjectId}
            />
          </div>

          {/* Two Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-slide-up" style={{ animationDelay: "0.3s" }}>
            <ApiKeySection />
            <UsageWidget />
          </div>
          
          {/* Legacy Usage Stats (keep for now) */}
          <div className="animate-slide-up" style={{ animationDelay: "0.35s" }}>
            <UsageStats />
          </div>

          {/* Billing */}
          <div className="animate-slide-up" style={{ animationDelay: "0.35s" }}>
            <BillingSection />
          </div>

          {/* Partner Program */}
          <div className="animate-slide-up" style={{ animationDelay: "0.4s" }}>
            <PartnerProgram />
          </div>

          {/* API Docs */}
          <div className="animate-slide-up" style={{ animationDelay: "0.45s" }}>
            <ApiDocs />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-6 mt-12 bg-card">
        <div className="container text-center text-sm text-muted-foreground">
          © 2025 LienDeadline. All rights reserved.
        </div>
      </footer>
      
      {/* Admin Simulator (only visible to admin) */}
      <AdminSimulator />

      {/* Admin Email Captures (only visible to admin) */}
      {planInfo?.isAdmin && (
        <div className="container py-8">
          <EmailCaptures />
        </div>
      )}
    </div>
  );
};

export default Index;
