import { useEffect } from "react";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { IntegrationsSection } from "@/components/dashboard/IntegrationsSection";
import { AccountOverview } from "@/components/dashboard/AccountOverview";
import { DeadlineCalculator } from "@/components/dashboard/DeadlineCalculator";
import { ProjectsTable } from "@/components/dashboard/ProjectsTable";
import { ApiKeySection } from "@/components/dashboard/ApiKeySection";
import { UsageStats } from "@/components/dashboard/UsageStats";
import { BillingSection } from "@/components/dashboard/BillingSection";
import { PartnerProgram } from "@/components/dashboard/PartnerProgram";
import { ApiDocs } from "@/components/dashboard/ApiDocs";

const Index = () => {
  useEffect(() => {
    fetch("/api/verify-session")
      .then(res => {
        if (!res.ok) window.location.href = "/login.html";
      })
      .catch(() => {
        window.location.href = "/login.html";
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

          {/* Account Overview */}
          <div className="animate-slide-up" style={{ animationDelay: "0.1s" }}>
            <AccountOverview />
          </div>

          {/* Deadline Calculator */}
          <div className="animate-slide-up" style={{ animationDelay: "0.15s" }}>
            <DeadlineCalculator />
          </div>

          {/* Integrations */}
          <div className="animate-slide-up" style={{ animationDelay: "0.2s" }}>
            <IntegrationsSection />
          </div>

          {/* Projects Table */}
          <div className="animate-slide-up" style={{ animationDelay: "0.25s" }}>
            <ProjectsTable />
          </div>

          {/* Two Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-slide-up" style={{ animationDelay: "0.3s" }}>
            <ApiKeySection />
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
    </div>
  );
};

export default Index;
