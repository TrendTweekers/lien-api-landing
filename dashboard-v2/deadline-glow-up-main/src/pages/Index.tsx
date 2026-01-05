import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Rocket } from "lucide-react";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { AccountOverview } from "@/components/dashboard/AccountOverview";
import { DeadlineCalculator } from "@/components/dashboard/DeadlineCalculator";
import { ProjectsTable } from "@/components/dashboard/ProjectsTable";
import { ApiKeySection } from "@/components/dashboard/ApiKeySection";
import { UsageStats } from "@/components/dashboard/UsageStats";
import { BillingSection } from "@/components/dashboard/BillingSection";
import { PartnerProgram } from "@/components/dashboard/PartnerProgram";
import { ApiDocs } from "@/components/dashboard/ApiDocs";
import UpgradePrompt from "@/components/UpgradePrompt";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

          {/* Zapier Automation Card - Small Summary */}
          <div className="animate-slide-up" style={{ animationDelay: "0.2s" }}>
            <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Zapier Automation</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* One-line value prop */}
                <p className="text-sm font-medium text-foreground">
                  Get deadline alerts wherever you already work.
                </p>
                
                {/* 3 bullets (concise) */}
                <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-2">
                  <li>Works with 6,000+ apps</li>
                  <li>No email setup inside LienDeadline</li>
                  <li>LienDeadline decides when — Zapier decides where</li>
                </ul>
                
                {/* Social proof */}
                <p className="text-xs text-muted-foreground italic">
                  Used by contractors protecting $2.3M+ in receivables monthly
                </p>

                {/* Two buttons */}
                <div className="flex flex-wrap gap-2 pt-2">
                  <Button
                    size="default"
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
                  </Button>
                  <Button
                    variant="outline"
                    size="default"
                    onClick={() => navigate('/zapier')}
                  >
                    Open Zapier Setup
                  </Button>
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
