import { Calculator, Zap, Calendar } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { usePlan } from "@/hooks/usePlan";

export const UsageWidget = () => {
  const { planInfo, loading } = usePlan();

  if (loading || !planInfo) {
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

  const formatDate = (dateStr: string | null | undefined) => {
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
            {planInfo.plan.charAt(0).toUpperCase() + planInfo.plan.slice(1)}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Manual Calculations */}
        {planInfo.plan === 'free' ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Calculator className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-foreground">Calculations</span>
            </div>
            <div className="text-right">
              <span className="text-sm font-medium">
                {planInfo.manualCalcUsed ?? 0}/{planInfo.manualCalcLimit ?? 3}
              </span>
              {planInfo.manualCalcRemaining !== null && planInfo.manualCalcRemaining !== undefined && (
                <span className="text-xs text-muted-foreground ml-2">
                  ({planInfo.manualCalcRemaining} remaining)
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
        {planInfo.plan === 'basic' ? (
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Zapier: Not included</span>
          </div>
        ) : planInfo.plan === 'automated' || planInfo.plan === 'enterprise' ? (
          <div className="flex items-center gap-2">
            <Zap className={`h-4 w-4 ${planInfo.zapierConnected ? 'text-success' : 'text-muted-foreground'}`} />
            <span className="text-sm text-foreground">Zapier: {planInfo.zapierConnected ? 'Connected' : 'Not connected'}</span>
          </div>
        ) : null}

        {/* API Calls (Automated plan) */}
        {planInfo.plan === 'automated' && planInfo.apiCallsLimit !== null && (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-foreground">API calls</span>
            </div>
            <div className="text-right">
              <span className="text-sm font-medium">
                {planInfo.apiCallsUsed ?? 0}/{planInfo.apiCallsLimit}
              </span>
              {planInfo.apiCallsRemaining !== null && planInfo.apiCallsRemaining !== undefined && (
                <span className="text-xs text-muted-foreground ml-2">
                  ({planInfo.apiCallsRemaining} remaining)
                </span>
              )}
            </div>
          </div>
        )}

        {/* Enterprise: Unlimited */}
        {planInfo.plan === 'enterprise' && (
          <div className="text-sm text-muted-foreground">Unlimited</div>
        )}

        {/* Reset Date */}
        {planInfo.resetDate && (
          <div className="flex items-center gap-2 pt-2 border-t border-border">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">
              Resets on {formatDate(planInfo.resetDate)}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

