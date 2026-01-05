import { useEffect, useState } from "react";
import { Calculator, Zap, Calendar } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface UsageStats {
  plan: string;
  manual_calc_used?: number;
  manual_calc_limit?: number;
  manual_calc_remaining?: number;
  api_calls_used?: number;
  api_calls_limit?: number;
  api_calls_remaining?: number;
  zapier_connected?: boolean;
  next_reset?: string;
}

export const UsageWidget = () => {
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const token = localStorage.getItem('session_token');
        if (!token) {
          setLoading(false);
          return;
        }

        const headers: HeadersInit = {
          "Authorization": `Bearer ${token}`
        };

        const res = await fetch('/api/user/stats', { headers });
        if (!res.ok) {
          setLoading(false);
          return;
        }

        const data = await res.json();
        setStats({
          plan: data.plan || data.subscriptionStatus || 'free',
          manual_calc_used: data.manual_calc_used ?? data.calculationsUsed ?? 0,
          manual_calc_limit: data.manual_calc_limit ?? data.calculationsLimit ?? null,
          manual_calc_remaining: data.manual_calc_remaining ?? data.calculationsRemaining ?? null,
          api_calls_used: data.api_calls_used ?? 0,
          api_calls_limit: data.api_calls_limit ?? null,
          api_calls_remaining: data.api_calls_remaining ?? null,
          zapier_connected: data.zapier_connected ?? false,
          next_reset: data.next_reset ?? null,
        });
      } catch (error) {
        console.error('Error fetching usage stats:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Usage</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading...</p>
        </CardContent>
      </Card>
    );
  }

  if (!stats) {
    return null;
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return null;
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch {
      return null;
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center justify-between">
          Usage
          <Badge variant="outline" className="text-xs">
            {stats.plan.charAt(0).toUpperCase() + stats.plan.slice(1)}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Manual Calculations */}
        {stats.plan === 'free' ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Calculator className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-foreground">Calculations</span>
            </div>
            <div className="text-right">
              <span className="text-sm font-medium">
                {stats.manual_calc_used ?? 0}/{stats.manual_calc_limit ?? 3}
              </span>
              {stats.manual_calc_remaining !== null && stats.manual_calc_remaining !== undefined && (
                <span className="text-xs text-muted-foreground ml-2">
                  ({stats.manual_calc_remaining} remaining)
                </span>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Calculator className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-foreground">Manual calculations: Unlimited</span>
          </div>
        )}

        {/* Zapier Status */}
        {stats.plan === 'basic' ? (
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Zapier: Not included</span>
          </div>
        ) : stats.plan === 'automated' || stats.plan === 'enterprise' ? (
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-success" />
            <span className="text-sm text-foreground">Zapier: Included</span>
          </div>
        ) : null}

        {/* API Calls (Automated plan) */}
        {stats.plan === 'automated' && stats.api_calls_limit !== null && (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-foreground">API calls</span>
            </div>
            <div className="text-right">
              <span className="text-sm font-medium">
                {stats.api_calls_used ?? 0}/{stats.api_calls_limit}
              </span>
              {stats.api_calls_remaining !== null && stats.api_calls_remaining !== undefined && (
                <span className="text-xs text-muted-foreground ml-2">
                  ({stats.api_calls_remaining} remaining)
                </span>
              )}
            </div>
          </div>
        )}

        {/* Enterprise: Unlimited */}
        {stats.plan === 'enterprise' && (
          <div className="text-sm text-muted-foreground">Unlimited</div>
        )}

        {/* Reset Date */}
        {stats.next_reset && (
          <div className="flex items-center gap-2 pt-2 border-t border-border">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">
              Resets on {formatDate(stats.next_reset)}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

