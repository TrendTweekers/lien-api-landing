import { useState, useEffect } from "react";
import { Mail, CheckCircle2, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { usePlan } from "@/hooks/usePlan";
import { useToast } from "@/hooks/use-toast";

export const EmailAlertsCard = () => {
  const { planInfo } = usePlan();
  const { toast } = useToast();
  const [alertEmail, setAlertEmail] = useState("");
  const [emailAlertsEnabled, setEmailAlertsEnabled] = useState(true);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Load preferences from planInfo
  useEffect(() => {
    if (planInfo.alertEmail !== undefined) {
      setAlertEmail(planInfo.alertEmail || "");
    }
    if (planInfo.emailAlertsEnabled !== undefined) {
      setEmailAlertsEnabled(planInfo.emailAlertsEnabled);
    }
  }, [planInfo.alertEmail, planInfo.emailAlertsEnabled]);

  const handleSave = async () => {
    if (!alertEmail.trim()) {
      toast({
        title: "Email required",
        description: "Please enter an email address for alerts",
        variant: "destructive",
      });
      return;
    }

    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(alertEmail)) {
      toast({
        title: "Invalid email",
        description: "Please enter a valid email address",
        variant: "destructive",
      });
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      };

      const res = await fetch('/api/user/preferences', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          alert_email: alertEmail.trim(),
          email_alerts_enabled: emailAlertsEnabled,
        }),
      });

      if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: "Failed to save preferences" }));
        throw new Error(error.detail || "Failed to save preferences");
      }

      toast({
        title: "Preferences saved",
        description: "Your email alert preferences have been updated",
      });

      // Refresh plan info to get updated values
      window.dispatchEvent(new Event('storage'));
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to save preferences",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-950 dark:to-blue-900 border-blue-200 dark:border-blue-800">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Mail className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          Email Alerts (Default)
        </CardTitle>
        <p className="text-sm text-muted-foreground mt-1">
          Get deadline reminders via email (7, 3, and 1 day before)
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="alert-email">Alert Email Address</Label>
          <Input
            id="alert-email"
            type="email"
            placeholder="your@email.com"
            value={alertEmail}
            onChange={(e) => setAlertEmail(e.target.value)}
            disabled={saving}
          />
        </div>

        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="email-alerts-enabled">Enable Email Alerts</Label>
            <p className="text-xs text-muted-foreground">
              Receive deadline reminders at 7, 3, and 1 day before
            </p>
          </div>
          <Switch
            id="email-alerts-enabled"
            checked={emailAlertsEnabled}
            onCheckedChange={setEmailAlertsEnabled}
            disabled={saving}
          />
        </div>

        <Button
          onClick={handleSave}
          disabled={saving || !alertEmail.trim()}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white"
        >
          {saving ? "Saving..." : "Save Preferences"}
        </Button>

        {emailAlertsEnabled && alertEmail && (
          <div className="flex items-start gap-2 p-3 bg-blue-50 dark:bg-blue-950 rounded-lg border border-blue-200 dark:border-blue-800">
            <CheckCircle2 className="h-4 w-4 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
            <div className="text-xs text-muted-foreground">
              <p className="font-medium text-foreground mb-1">Email alerts active</p>
              <p>You'll receive reminders at {alertEmail} for deadlines 7, 3, and 1 day before they're due.</p>
            </div>
          </div>
        )}

        {!emailAlertsEnabled && alertEmail && (
          <div className="flex items-start gap-2 p-3 bg-muted/50 rounded-lg border border-border">
            <AlertCircle className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
            <div className="text-xs text-muted-foreground">
              <p className="font-medium text-foreground mb-1">Email alerts disabled</p>
              <p>Enable the toggle above to start receiving deadline reminders.</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

