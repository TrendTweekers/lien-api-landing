import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Rocket } from "lucide-react";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { EnhancedAccountOverview } from "@/components/dashboard/EnhancedAccountOverview";
import { UrgentProjectsCards } from "@/components/dashboard/UrgentProjectsCards";
import { DeadlineCalculator } from "@/components/dashboard/DeadlineCalculator";
import { ProjectsTable } from "@/components/dashboard/ProjectsTable";
import { ProjectsSection } from "@/components/dashboard/ProjectsSection";
import { ApiKeySection } from "@/components/dashboard/ApiKeySection";
import { UsageStats } from "@/components/dashboard/UsageStats";
import { UsageWidget } from "@/components/dashboard/UsageWidget";
import { BillingSection } from "@/components/dashboard/BillingSection";
import { PartnerProgram } from "@/components/dashboard/PartnerProgram";
import { ApiDocs } from "@/components/dashboard/ApiDocs";
import UpgradePrompt from "@/components/UpgradePrompt";
import { ZapierStatusCard } from "@/components/dashboard/ZapierStatusCard";
import { EmailAlertsCard } from "@/components/dashboard/EmailAlertsCard";
import { AdminSimulator } from "@/components/AdminSimulator";
import { EmailCaptures } from "@/components/admin/EmailCaptures";
import { usePlan } from "@/hooks/usePlan";

const Index = () => {
  const navigate = useNavigate();
  const { planInfo, loading: planLoading } = usePlan();
  const [expandedProjectId, setExpandedProjectId] = useState<number | null>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);

  // SINGLE API CALL - Fetch once, use everywhere (PERFORMANCE OPTIMIZATION)
  const fetchProjects = async () => {
    setLoadingProjects(true);
    try {
      const token = localStorage.getItem('session_token');
      const response = await fetch("/api/calculations/history", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      const data = await response.json();
      setProjects(Array.isArray(data.history) ? data.history : []);
    } catch (error) {
      console.error('Error fetching projects:', error);
      setProjects([]);
    } finally {
      setLoadingProjects(false);
    }
  };

  useEffect(() => {
    // Check for session token
    const token = localStorage.getItem('session_token');
    if (!token) {
      window.location.href = '/login.html';
      return;
    }
    
    // Verify session only once (usePlan will handle stats)
    fetch('/api/verify-session', {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(res => {
      if (!res.ok) {
        window.location.href = '/login.html';
      }
    }).catch(() => {
      window.location.href = '/login.html';
    });

    // Fetch projects once
    fetchProjects();
  }, []);

  if (planLoading || loadingProjects) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

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
          {!planLoading && planInfo && planInfo.plan === 'free' && (
            <UpgradePrompt 
              calculationsUsed={planInfo.manualCalcUsed || 0}
              calculationsLimit={planInfo.manualCalcLimit || 3}
            />
          )}

          {/* Enhanced Account Overview */}
          <div className="animate-slide-up" style={{ animationDelay: "0.1s" }}>
            <EnhancedAccountOverview />
          </div>

          {/* Deadline Calculator */}
          <div className="animate-slide-up" style={{ animationDelay: "0.15s" }}>
            <DeadlineCalculator 
              onCalculationComplete={fetchProjects} 
            />
          </div>

          {/* Email Alerts Card (Default Path) */}
          <div className="animate-slide-up" style={{ animationDelay: "0.18s" }}>
            <EmailAlertsCard />
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

          {/* Urgent Projects Cards */}
          <div className="animate-slide-up" style={{ animationDelay: "0.22s" }}>
            <UrgentProjectsCards 
              projects={projects}
              userTier={planInfo?.plan || 'free'}
            />
          </div>

          {/* Projects Section with Table/Card Toggle */}
          <div className="animate-slide-up" style={{ animationDelay: "0.25s" }}>
            <ProjectsSection
              projects={projects}
              userTier={planInfo?.plan || 'free'}
              onRefresh={fetchProjects}
              ProjectsTableComponent={() => (
                <ProjectsTable 
                  expandedProjectId={expandedProjectId}
                  onExpandedProjectChange={setExpandedProjectId}
                />
              )}
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
