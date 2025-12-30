import { BarChart3, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useState, useEffect } from "react";
import { toast } from "sonner";

interface Calculation {
  created_at: string;
  state_code?: string;
  state?: string;
}

export const UsageStats = () => {
  const [stats, setStats] = useState({
    count: 0,
    states: [] as string[]
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUsage = async () => {
      try {
        const token = localStorage.getItem('session_token');
        const headers: HeadersInit = {
          "Content-Type": "application/json",
        };
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch("/api/calculations/history", { headers });
        if (!res.ok) throw new Error("Failed to fetch usage stats");
        
        const data = await res.json();
        const history: Calculation[] = data.history || [];
        
        // Filter for last 30 days
        const thirtyDaysAgo = new Date();
        thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
        
        const recentCalculations = history.filter(item => {
          if (!item.created_at) return false;
          return new Date(item.created_at) > thirtyDaysAgo;
        });

        // Get unique states
        const uniqueStates = Array.from(new Set(
          recentCalculations
            .map(item => item.state_code || item.state)
            .filter(Boolean)
        )) as string[];

        setStats({
          count: recentCalculations.length,
          states: uniqueStates.slice(0, 5) // Limit to top 5 to fit UI
        });
      } catch (error) {
        console.error("Error fetching usage stats:", error);
        // Don't show toast error to avoid annoying users if stats fail, just show 0
      } finally {
        setLoading(false);
      }
    };

    fetchUsage();
  }, []);

  if (loading) {
    return (
      <div className="bg-card rounded-xl p-6 border border-border card-shadow h-[200px] flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-xl p-6 border border-border card-shadow">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-lg bg-info/15 flex items-center justify-center">
          <BarChart3 className="h-5 w-5 text-info" />
        </div>
        <h2 className="text-lg font-semibold text-foreground">Usage This Month</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <p className="text-sm text-muted-foreground mb-2">Total API Calls</p>
          <p className="text-4xl font-bold text-primary">{stats.count.toLocaleString()}</p>
          <p className="text-xs text-muted-foreground mt-1">Last 30 days</p>
        </div>

        <div>
          <p className="text-sm text-muted-foreground mb-2 flex items-center gap-1">
            <MapPin className="h-4 w-4" />
            States Used
          </p>
          <div className="flex flex-wrap gap-2">
            {stats.states.length > 0 ? (
              stats.states.map((state) => (
                <Badge
                  key={state}
                  variant="outline"
                  className="bg-muted border-border text-foreground px-3 py-1 font-medium"
                >
                  {state}
                </Badge>
              ))
            ) : (
              <span className="text-sm text-muted-foreground">No usage yet</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
