import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Rocket, ExternalLink } from "lucide-react";
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
import UpgradePrompt from "@/components/UpgradePrompt";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const Index = () => {
  const navigate = useNavigate();
  const [userStats, setUserStats] = useState<{
    calculationsUsed: number;
    calculationsLimit: number | null;
    subscriptionStatus: string;
  } | null>(null);

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

          {/* Zapier Automation Card */}
          <div className="animate-slide-up" style={{ animationDelay: "0.2s" }}>
            <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
              <CardHeader>
                <CardTitle className="text-2xl">Zapier Automation</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Value Proposition */}
                <div className="space-y-4">
                  <h3 className="text-xl font-semibold text-foreground">
                    Get deadline alerts wherever you already work
                  </h3>
                  <p className="text-muted-foreground">
                    Connect Zapier in minutes to send lien deadline reminders to Slack, email, CRM, or spreadsheets — powered by Zapier.
                  </p>
                  
                  <ul className="list-disc list-inside space-y-2 text-muted-foreground ml-2">
                    <li>Works with 6,000+ apps</li>
                    <li>No email setup inside LienDeadline</li>
                    <li>LienDeadline decides when — Zapier decides where</li>
                  </ul>
                  
                  <p className="text-sm text-muted-foreground italic">
                    Used by contractors protecting $2.3M+ in receivables monthly
                  </p>
                </div>

                {/* Quick Start Block */}
                <div className="bg-card rounded-lg p-4 border border-border">
                  <div className="flex items-center gap-2 mb-2">
                    <Rocket className="h-5 w-5 text-primary" />
                    <h4 className="font-semibold text-foreground">🚀 Quick Start with Slack</h4>
                  </div>
                  <p className="text-sm text-muted-foreground mb-4">
                    Get your first alert in under 5 minutes
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <Button
                      size="lg"
                      onClick={() => {
                        navigate('/zapier#quick-start');
                        // Scroll to quick-start after navigation
                        setTimeout(() => {
                          const element = document.getElementById('quick-start');
                          if (element) {
                            element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                          }
                        }, 100);
                      }}
                    >
                      Quick Start with Slack
                      <ExternalLink className="h-4 w-4 ml-2" />
                    </Button>
                    <Button
                      variant="outline"
                      size="lg"
                      onClick={() => navigate('/zapier')}
                    >
                      Open Zapier Setup
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
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
