import { useEffect, useState } from "react";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { StatsCards } from "@/components/dashboard/StatsCards";
import { ReferralsTable } from "@/components/dashboard/ReferralsTable";
import { MarketingTools } from "@/components/dashboard/MarketingTools";
import { PaymentSettings } from "@/components/dashboard/PaymentSettings";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

const Index = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      const token = localStorage.getItem("broker_token");
      const email = localStorage.getItem("broker_email");

      if (!token || !email) {
        navigate("/login");
        return;
      }

      try {
        const response = await fetch(`/api/v1/broker/dashboard?email=${encodeURIComponent(email)}`, {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });

        if (response.status === 401) {
          localStorage.removeItem("broker_token");
          navigate("/login");
          return;
        }

        const dashboardData = await response.json();
        
        if (response.ok) {
          setData(dashboardData);
        } else {
          toast.error(dashboardData.message || "Failed to load dashboard");
        }
      } catch (error) {
        console.error("Dashboard error:", error);
        toast.error("Failed to connect to server");
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, [navigate]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <DashboardHeader />
      
      <main className="container py-8 space-y-8">
        {/* Welcome */}
        <div className="animate-fade-in">
          <h1 className="text-3xl font-bold text-foreground mb-2">
            Welcome back, <span className="text-primary">{data?.broker_name || "Partner"}</span>
          </h1>
          <p className="text-muted-foreground">
            Track your referrals and earnings.
          </p>
        </div>

        {/* Stats */}
        <div className="animate-slide-up" style={{ animationDelay: "0.1s" }}>
          <StatsCards 
            totalReferrals={data?.total_referrals || 0}
            totalPending={data?.total_pending || 0}
            totalPaid={data?.total_paid || 0}
          />
        </div>

        {/* Main Content Tabs */}
        <div className="animate-slide-up" style={{ animationDelay: "0.2s" }}>
          <Tabs defaultValue="referrals" className="space-y-4">
            <TabsList>
              <TabsTrigger value="referrals">Referrals</TabsTrigger>
              <TabsTrigger value="marketing">Marketing Tools</TabsTrigger>
              <TabsTrigger value="settings">Payment Settings</TabsTrigger>
            </TabsList>

            <TabsContent value="referrals" className="space-y-4">
              <ReferralsTable referrals={data?.referrals || []} />
            </TabsContent>

            <TabsContent value="marketing" className="space-y-4">
              <MarketingTools 
                referralLink={data?.referral_link || ""} 
                brokerName={data?.broker_name || "Partner"}
              />
            </TabsContent>

            <TabsContent value="settings" className="space-y-4">
              <PaymentSettings email={localStorage.getItem("broker_email") || ""} />
            </TabsContent>
          </Tabs>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-6 mt-12 bg-card">
        <div className="container text-center text-sm text-muted-foreground">
          © 2025 LienDeadline Partner Program. All rights reserved.
        </div>
      </footer>
    </div>
  );
};

export default Index;
