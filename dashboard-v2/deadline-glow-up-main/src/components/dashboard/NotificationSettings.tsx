import { useState, useEffect } from "react";
import { Zap, Save, AlertCircle, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { usePlan } from "@/hooks/usePlan";

interface NotificationSettingsProps {
  projectId: string;
  projectName?: string;
}

export const NotificationSettings = ({ projectId, projectName }: NotificationSettingsProps) => {
  const { toast } = useToast();
  const { planInfo } = usePlan();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reminderOffsets, setReminderOffsets] = useState<number[]>([]);
  const [zapierEnabled, setZapierEnabled] = useState(false);
  const [zapierConnected, setZapierConnected] = useState(false);
  const [loadingZapierStatus, setLoadingZapierStatus] = useState(true);
  const [zapierStatusError, setZapierStatusError] = useState(false);

  // Hard stop: Only fetch if plan is eligible
  const notificationsEligible = planInfo?.plan === "automated" || planInfo?.plan === "enterprise";

  // Available offset options
  const availableOffsets = [1, 7, 14];

  // Load Zapier connection status (only if eligible)
  useEffect(() => {
    if (!notificationsEligible) {
      setLoadingZapierStatus(false);
      setZapierConnected(false);
      return;
    }
    loadZapierStatus();
  }, [notificationsEligible]);

  // Load notification settings only when eligible and Zapier status is loaded
  useEffect(() => {
    if (!notificationsEligible) return;
    if (zapierConnected === undefined) return;
    
    loadSettings();
  }, [projectId, zapierConnected, notificationsEligible]);

  const loadZapierStatus = async () => {
    setLoadingZapierStatus(true);
    setZapierStatusError(false);
    try {
      const token = localStorage.getItem('session_token');
      if (!token) {
        setZapierConnected(false);
        setLoadingZapierStatus(false);
        setZapierStatusError(true);
        return;
      }

      const headers: HeadersInit = {
        "Authorization": `Bearer ${token}`
      };

      const res = await fetch(`/api/user/stats`, { headers });
      if (!res.ok) {
        // If 401, token might be invalid - default to false
        if (res.status === 401) {
          setZapierConnected(false);
          setZapierStatusError(true);
          return;
        }
        throw new Error(`Failed to load Zapier status: ${res.status}`);
      }

      const data = await res.json();
      setZapierConnected(data.zapier_connected === true);
      setZapierStatusError(false);
    } catch (error) {
      // Silently default to false - don't spam console
      setZapierConnected(false);
      setZapierStatusError(true);
    } finally {
      setLoadingZapierStatus(false);
    }
  };

  const loadSettings = async () => {
    // Hard stop: Only fetch if plan is eligible
    if (!notificationsEligible) {
      return;
    }

    setLoading(true);
    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = {
        "Content-Type": "application/json"
      };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`/api/projects/${projectId}/notifications`, { headers });
      
      // If 403, stop permanently - user is not eligible
      if (res.status === 403) {
        setLoading(false);
        return;
      }
      
      if (!res.ok) {
        throw new Error("Failed to load settings");
      }

      const data = await res.json();
      setReminderOffsets(data.reminder_offsets_days || [7]);
      setZapierEnabled(data.zapier_enabled || false);
    } catch (error) {
      // Silently fail - don't spam console
      // Set defaults
      setReminderOffsets([7]);
      setZapierEnabled(false);
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    if (!zapierConnected) {
      toast({
        title: "Zapier not connected",
        description: "Please connect Zapier first to enable reminders.",
        variant: "destructive",
      });
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = {
        "Content-Type": "application/json"
      };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`/api/projects/${projectId}/notifications`, {
        method: "PUT",
        headers,
        body: JSON.stringify({
          reminder_offsets_days: reminderOffsets,
          zapier_enabled: zapierEnabled
        })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: "Failed to save settings" }));
        throw new Error(errorData.detail || "Failed to save notification settings");
      }

      toast({
        title: "Settings saved",
        description: "Notification settings updated successfully.",
      });
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to save notification settings.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const toggleOffset = (offsetDays: number) => {
    if (!zapierConnected) return;
    
    setReminderOffsets(prev => {
      if (prev.includes(offsetDays)) {
        return prev.filter(d => d !== offsetDays);
      } else {
        return [...prev, offsetDays].sort((a, b) => a - b);
      }
    });
  };

  const scrollToZapier = () => {
    // Navigate to Zapier dashboard page
    window.location.href = '/dashboard/zapier';
  };

  const isOffsetEnabled = (offsetDays: number) => {
    return reminderOffsets.includes(offsetDays);
  };

  const isDisabled = !zapierConnected || loadingZapierStatus;

  return (
    <div className="bg-muted/30 rounded-lg p-4 border border-border space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h4 className="text-sm font-semibold text-foreground mb-1">Notification Settings</h4>
          <p className="text-xs text-muted-foreground">
            Configure reminder offsets for Zapier delivery. Zapier will send email/Slack/etc.
          </p>
        </div>
      </div>

      {loadingZapierStatus || loading ? (
        <div className="text-sm text-muted-foreground py-4">Loading settings...</div>
      ) : !zapierConnected ? (
        <div className="space-y-4">
          <div className="flex items-start gap-2 p-3 bg-warning/10 border border-warning/30 rounded-md">
            <AlertCircle className="h-4 w-4 text-warning mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-xs font-medium text-foreground mb-1">Zapier not connected</p>
              <p className="text-xs text-muted-foreground mb-3">
                Connect Zapier to enable reminders. Zapier will deliver email/Slack/etc.
              </p>
              <Button
                size="sm"
                onClick={scrollToZapier}
                className="bg-primary hover:bg-primary/90 text-primary-foreground"
              >
                <ExternalLink className="h-3 w-3 mr-1" />
                Connect Zapier
              </Button>
            </div>
          </div>
          {zapierStatusError && (
            <p className="text-xs text-muted-foreground italic">
              Could not verify Zapier connection
            </p>
          )}
        </div>
      ) : (
        <>
          {/* Zapier Toggle */}
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-background rounded-md border border-border">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-muted-foreground" />
                <Label htmlFor={`zapier-enabled-${projectId}`} className="text-sm font-medium text-foreground cursor-pointer">
                  Send via Zapier
                </Label>
              </div>
              <Switch
                id={`zapier-enabled-${projectId}`}
                checked={zapierEnabled}
                onCheckedChange={setZapierEnabled}
                disabled={isDisabled}
              />
            </div>
          </div>

          {/* Offset Toggles */}
          {zapierEnabled && (
            <div className="space-y-3 pt-2 border-t border-border">
              <Label className="text-xs font-medium text-foreground">Reminder Offsets</Label>
              <div className="flex flex-wrap gap-2">
                {availableOffsets.map(offset => {
                  const isEnabled = isOffsetEnabled(offset);
                  return (
                    <div
                      key={offset}
                      className={`flex items-center gap-2 px-3 py-2 rounded-md border cursor-pointer transition-colors ${
                        isEnabled
                          ? "bg-primary/10 border-primary text-primary"
                          : "bg-background border-border text-muted-foreground hover:border-primary/50"
                      } ${isDisabled ? "opacity-50 cursor-not-allowed" : ""}`}
                      onClick={() => !isDisabled && toggleOffset(offset)}
                    >
                      <input
                        type="checkbox"
                        checked={isEnabled}
                        onChange={() => !isDisabled && toggleOffset(offset)}
                        disabled={isDisabled}
                        className="h-3 w-3 rounded border-gray-300 text-primary focus:ring-primary"
                      />
                      <span className="text-xs font-medium">{offset} {offset === 1 ? 'Day' : 'Days'}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Helper Text */}
          {zapierEnabled && reminderOffsets.length > 0 && (
            <div className="flex items-start gap-2 p-2 bg-info/10 border border-info/30 rounded-md">
              <AlertCircle className="h-3 w-3 text-info mt-0.5 flex-shrink-0" />
              <p className="text-xs text-muted-foreground">
                If no reminders are due, Zapier will not send anything.
              </p>
            </div>
          )}

          {/* Save Button */}
          <div className="flex justify-end pt-2 border-t border-border">
            <Button
              size="sm"
              onClick={saveSettings}
              disabled={saving || isDisabled || !zapierEnabled || reminderOffsets.length === 0}
              className="bg-primary hover:bg-primary/90 text-primary-foreground"
            >
              {saving ? (
                <>
                  <div className="h-3 w-3 mr-2 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-3 w-3 mr-1" />
                  Save Settings
                </>
              )}
            </Button>
          </div>
        </>
      )}
    </div>
  );
};
