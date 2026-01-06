import { useState, useEffect } from "react";
import { Settings, Zap, Calculator, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { usePlan, PlanType } from "@/hooks/usePlan";

export const AdminSimulator = () => {
  const { planInfo } = usePlan();
  const [simulatedPlan, setSimulatedPlan] = useState<PlanType>("free");
  const [simulatedRemaining, setSimulatedRemaining] = useState<number>(3);
  const [simulatedManualUsed, setSimulatedManualUsed] = useState<number>(0);
  const [simulatedApiUsed, setSimulatedApiUsed] = useState<number>(0);
  const [simulatedZapier, setSimulatedZapier] = useState<boolean>(false);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!planInfo.isAdmin) return;

        try {
          const simData = localStorage.getItem('admin_billing_sim');
          if (simData) {
            const parsed = JSON.parse(simData);
            // Support both old and new format for backward compatibility
            if (parsed.plan || parsed.simulated_plan) {
              setSimulatedPlan((parsed.plan || parsed.simulated_plan) as PlanType);
              setSimulatedRemaining(parsed.remainingCalculations ?? parsed.simulated_remaining_calculations ?? 3);
              setSimulatedManualUsed(parsed.simulated_manual_used ?? 0);
              setSimulatedApiUsed(parsed.apiCallsUsed ?? parsed.simulated_api_used ?? 0);
              setSimulatedZapier(parsed.zapierConnected ?? parsed.simulated_zapier_connected ?? false);
            }
          }
        } catch (e) {
          console.error('Error loading admin simulator:', e);
        }
  }, [planInfo.isAdmin]);

  if (!planInfo.isAdmin) {
    return null;
  }

  const handleSave = () => {
    const simData = {
      plan: simulatedPlan,
      remainingCalculations: simulatedRemaining,
      apiCallsUsed: simulatedApiUsed,
      zapierConnected: simulatedZapier,
      active: true
    };
    localStorage.setItem('admin_billing_sim', JSON.stringify(simData));
    // Broadcast event to notify usePlan hook
    window.dispatchEvent(new Event('admin-billing-sim-updated'));
    setIsOpen(false);
  };

  const handleClear = () => {
    localStorage.removeItem('admin_billing_sim');
    setSimulatedPlan("free");
    setSimulatedRemaining(3);
    setSimulatedManualUsed(0);
    setSimulatedApiUsed(0);
    setSimulatedZapier(false);
    // Broadcast event to notify usePlan hook
    window.dispatchEvent(new Event('admin-billing-sim-updated'));
    setIsOpen(false);
  };

  return (
    <>
      {/* Floating toggle button */}
      <div className="fixed bottom-4 right-4 z-50">
        <Button
          onClick={() => setIsOpen(!isOpen)}
          className="rounded-full shadow-lg"
          size="sm"
          variant="outline"
        >
          <Settings className="h-4 w-4 mr-2" />
          Admin Sim
          {planInfo.isSimulated && (
            <Badge className="ml-2 bg-orange-500">ACTIVE</Badge>
          )}
        </Button>
      </div>

      {/* Simulator panel */}
      {isOpen && (
        <div className="fixed bottom-20 right-4 z-50 w-96">
          <Card className="shadow-2xl border-2 border-orange-500">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Settings className="h-5 w-5 text-orange-500" />
                  Admin Billing Simulator
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsOpen(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Override billing state for testing
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="sim-plan">Simulated Plan</Label>
                <Select
                  value={simulatedPlan}
                  onValueChange={(value) => setSimulatedPlan(value as PlanType)}
                >
                  <SelectTrigger id="sim-plan">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="free">Free</SelectItem>
                    <SelectItem value="basic">Basic ($49/month)</SelectItem>
                    <SelectItem value="automated">Automated ($149/month)</SelectItem>
                    <SelectItem value="enterprise">Enterprise ($499/month)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="sim-remaining">Remaining Calculations</Label>
                <Input
                  id="sim-remaining"
                  type="number"
                  value={simulatedRemaining}
                  onChange={(e) => setSimulatedRemaining(parseInt(e.target.value) || 0)}
                  min={0}
                  max={999}
                />
              </div>

              <div>
                <Label htmlFor="sim-manual-used">Manual Calculations Used</Label>
                <Input
                  id="sim-manual-used"
                  type="number"
                  value={simulatedManualUsed}
                  onChange={(e) => setSimulatedManualUsed(parseInt(e.target.value) || 0)}
                  min={0}
                  max={999}
                />
              </div>

              <div>
                <Label htmlFor="sim-api-used">API Calls Used</Label>
                <Input
                  id="sim-api-used"
                  type="number"
                  value={simulatedApiUsed}
                  onChange={(e) => setSimulatedApiUsed(parseInt(e.target.value) || 0)}
                  min={0}
                  max={999}
                />
              </div>

              <div className="flex items-center justify-between">
                <Label htmlFor="sim-zapier" className="flex items-center gap-2">
                  <Zap className="h-4 w-4" />
                  Zapier Connected
                </Label>
                <Switch
                  id="sim-zapier"
                  checked={simulatedZapier}
                  onCheckedChange={setSimulatedZapier}
                />
              </div>

              <div className="flex gap-2 pt-2">
                <Button onClick={handleSave} className="flex-1">
                  Apply
                </Button>
                <Button onClick={handleClear} variant="outline">
                  Clear
                </Button>
              </div>

              {planInfo.isSimulated && (
                <div className="mt-2 p-2 bg-orange-50 border border-orange-200 rounded text-xs">
                  <p className="font-semibold text-orange-800">Simulator Active</p>
                  <p className="text-orange-700">
                    Plan: {planInfo.plan} • Remaining: {planInfo.remainingCalculations} • Zapier: {planInfo.zapierConnected ? "Yes" : "No"}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
};

