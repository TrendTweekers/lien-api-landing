import { useState, useEffect } from "react";
import { Bell, Mail, MessageSquare, Zap, Save, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ChevronDown, ChevronUp } from "lucide-react";

interface ReminderConfig {
  offset_days: number;
  channels: {
    email: boolean;
    slack: boolean;
    zapier: boolean;
  };
}

interface NotificationSettingsProps {
  projectId: number;
  projectName?: string;
}

export const NotificationSettings = ({ projectId, projectName }: NotificationSettingsProps) => {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [reminders, setReminders] = useState<ReminderConfig[]>([]);
  const [hasZapierEnabled, setHasZapierEnabled] = useState(false);

  // Available offset options
  const availableOffsets = [1, 7, 14];

  // Load notification settings
  useEffect(() => {
    if (isOpen) {
      loadSettings();
    }
  }, [isOpen, projectId]);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = {
        "Content-Type": "application/json"
      };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`/api/projects/${projectId}/notifications`, { headers });
      if (!res.ok) throw new Error("Failed to load settings");

      const data = await res.json();
      const loadedReminders = data.reminders || [];
      
      // Ensure we have at least the default (7 days, email only)
      if (loadedReminders.length === 0) {
        loadedReminders.push({
          offset_days: 7,
          channels: { email: true, slack: false, zapier: false }
        });
      }

      setReminders(loadedReminders);
      
      // Check if any reminder has zapier enabled
      const zapierEnabled = loadedReminders.some((r: ReminderConfig) => r.channels.zapier);
      setHasZapierEnabled(zapierEnabled);
    } catch (error) {
      console.error("Error loading notification settings:", error);
      // Set default if load fails
      setReminders([{
        offset_days: 7,
        channels: { email: true, slack: false, zapier: false }
      }]);
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
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
        body: JSON.stringify({ reminders })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: "Failed to save settings" }));
        throw new Error(errorData.detail || "Failed to save settings");
      }

      // Check if zapier is enabled
      const zapierEnabled = reminders.some(r => r.channels.zapier);
      setHasZapierEnabled(zapierEnabled);

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
    setReminders(prev => {
      const existing = prev.find(r => r.offset_days === offsetDays);
      if (existing) {
        // Remove if exists
        return prev.filter(r => r.offset_days !== offsetDays);
      } else {
        // Add with default channels (email=true, others=false)
        return [...prev, {
          offset_days: offsetDays,
          channels: { email: true, slack: false, zapier: false }
        }];
      }
    });
  };

  const updateChannel = (offsetDays: number, channel: 'email' | 'slack' | 'zapier', value: boolean) => {
    setReminders(prev => {
      const updated = prev.map(r => {
        if (r.offset_days === offsetDays) {
          return {
            ...r,
            channels: { ...r.channels, [channel]: value }
          };
        }
        return r;
      });
      // Update hasZapierEnabled based on updated reminders
      const zapierEnabled = updated.some(r => r.channels.zapier);
      setHasZapierEnabled(zapierEnabled);
      return updated;
    });
  };

  const getReminderConfig = (offsetDays: number): ReminderConfig | undefined => {
    return reminders.find(r => r.offset_days === offsetDays);
  };

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          <Bell className="h-3 w-3 mr-1" />
          Notifications
          {isOpen ? <ChevronUp className="h-3 w-3 ml-1" /> : <ChevronDown className="h-3 w-3 ml-1" />}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2">
        <div className="bg-muted/30 rounded-lg p-4 border border-border space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <h4 className="text-sm font-semibold text-foreground mb-1">Notification Settings</h4>
              <p className="text-xs text-muted-foreground">
                Notifications are configured per project. Configure reminder offsets and delivery channels.
              </p>
            </div>
          </div>

          {loading ? (
            <div className="text-sm text-muted-foreground py-4">Loading settings...</div>
          ) : (
            <>
              {/* Offset Toggles */}
              <div className="space-y-3">
                <Label className="text-xs font-medium text-foreground">Reminder Offsets</Label>
                <div className="flex flex-wrap gap-2">
                  {availableOffsets.map(offset => {
                    const config = getReminderConfig(offset);
                    const isEnabled = !!config;
                    return (
                      <div
                        key={offset}
                        className={`flex items-center gap-2 px-3 py-2 rounded-md border cursor-pointer transition-colors ${
                          isEnabled
                            ? "bg-primary/10 border-primary text-primary"
                            : "bg-background border-border text-muted-foreground hover:border-primary/50"
                        }`}
                        onClick={() => toggleOffset(offset)}
                      >
                        <input
                          type="checkbox"
                          checked={isEnabled}
                          onChange={() => toggleOffset(offset)}
                          className="h-3 w-3 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                        <span className="text-xs font-medium">{offset} {offset === 1 ? 'Day' : 'Days'}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Channel Settings for Each Enabled Offset */}
              {reminders.length > 0 && (
                <div className="space-y-3 pt-2 border-t border-border">
                  <Label className="text-xs font-medium text-foreground">Delivery Channels</Label>
                  <div className="space-y-3">
                    {reminders.map(reminder => (
                      <div key={reminder.offset_days} className="bg-background rounded-md p-3 border border-border">
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-xs font-semibold text-foreground">
                            {reminder.offset_days} {reminder.offset_days === 1 ? 'Day' : 'Days'} Before Deadline
                          </span>
                        </div>
                        <div className="space-y-2">
                          {/* Email */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <Mail className="h-3 w-3 text-muted-foreground" />
                              <Label htmlFor={`email-${reminder.offset_days}`} className="text-xs text-foreground cursor-pointer">
                                Email
                              </Label>
                            </div>
                            <Switch
                              id={`email-${reminder.offset_days}`}
                              checked={reminder.channels.email}
                              onCheckedChange={(checked) => updateChannel(reminder.offset_days, 'email', checked)}
                            />
                          </div>

                          {/* Slack */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <MessageSquare className="h-3 w-3 text-muted-foreground" />
                              <Label htmlFor={`slack-${reminder.offset_days}`} className="text-xs text-foreground cursor-pointer">
                                Slack
                              </Label>
                            </div>
                            <Switch
                              id={`slack-${reminder.offset_days}`}
                              checked={reminder.channels.slack}
                              onCheckedChange={(checked) => updateChannel(reminder.offset_days, 'slack', checked)}
                            />
                          </div>

                          {/* Zapier */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <Zap className="h-3 w-3 text-muted-foreground" />
                              <Label htmlFor={`zapier-${reminder.offset_days}`} className="text-xs text-foreground cursor-pointer">
                                Zapier
                              </Label>
                            </div>
                            <Switch
                              id={`zapier-${reminder.offset_days}`}
                              checked={reminder.channels.zapier}
                              onCheckedChange={(checked) => {
                                updateChannel(reminder.offset_days, 'zapier', checked);
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Helper Text for Zapier */}
              {hasZapierEnabled && (
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
                  disabled={saving || reminders.length === 0}
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
      </CollapsibleContent>
    </Collapsible>
  );
};

