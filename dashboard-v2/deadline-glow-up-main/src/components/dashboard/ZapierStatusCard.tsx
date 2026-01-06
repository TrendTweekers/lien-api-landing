import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Zap, Bell, Rocket, ExternalLink, Lock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { usePlan } from "@/hooks/usePlan";
import { UpgradeModal } from "@/components/UpgradeModal";

interface Project {
  id: number;
}

interface ProjectNotificationStatus {
  projectId: number;
  zapierEnabled: boolean;
  reminderOffsetsDays: number[];
}

interface ZapierStatusCardProps {
  onProjectExpand?: (projectId: number) => void;
}

export const ZapierStatusCard = ({ onProjectExpand }: ZapierStatusCardProps) => {
  const navigate = useNavigate();
  const { planInfo } = usePlan();
  const [zapierConnected, setZapierConnected] = useState<boolean | null>(null);
  const [lastStatusCheckAt, setLastStatusCheckAt] = useState<Date | null>(null);
  const [projectsWithAlerts, setProjectsWithAlerts] = useState(0);
  const [projectsNeedingSetup, setProjectsNeedingSetup] = useState(0);
  const [totalProjects, setTotalProjects] = useState(0);
  const [firstProjectNeedingSetup, setFirstProjectNeedingSetup] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);
  
  // Check if Zapier is locked (free or basic plan)
  const isZapierLocked = planInfo.plan === "free" || planInfo.plan === "basic";

  // Format relative time
  const formatRelativeTime = (date: Date | null): string => {
    if (!date) return "—";
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return "just now";
    if (diffMins === 1) return "1m ago";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours === 1) return "1h ago";
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return "1d ago";
    return `${diffDays}d ago`;
  };

  // Fetch Zapier connection status - use planInfo from usePlan hook
  useEffect(() => {
    // Use zapierConnected from planInfo (already fetched by usePlan)
    const connected = planInfo.zapierConnected;
    setZapierConnected(connected);
    setLastStatusCheckAt(planInfo.lastSyncAt || new Date());
    
    // Only fetch project notifications if Zapier is connected and plan allows it
    if (!isZapierLocked && connected) {
      fetchProjectsNotificationStatus();
    } else {
      // If not connected or locked, still fetch project count
      fetchProjectsCount();
    }
    setLoading(false);
  }, [planInfo.zapierConnected, planInfo.lastSyncAt, isZapierLocked]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch project count only (when Zapier not connected)
  const fetchProjectsCount = async () => {
    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("/api/calculations/history", { headers });
      if (!res.ok) return;
      
      const data = await res.json();
      const historyArray = Array.isArray(data.history) ? data.history : (Array.isArray(data) ? data : []);
      setTotalProjects(historyArray.length);
      setProjectsNeedingSetup(historyArray.length);
      setProjectsWithAlerts(0);
    } catch (error) {
      console.error('Error fetching projects count:', error);
    }
  };

  // Fetch notification status for all projects
  const fetchProjectsNotificationStatus = async () => {
    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      // Fetch projects list
      const res = await fetch("/api/calculations/history", { headers });
      if (!res.ok) return;
      
      const data = await res.json();
      const historyArray = Array.isArray(data.history) ? data.history : (Array.isArray(data) ? data : []);
      const projects: Project[] = historyArray;
      setTotalProjects(projects.length);

      // Fetch notification settings for all projects in parallel
      const notificationPromises = projects.map(async (project) => {
        try {
          const notifRes = await fetch(`/api/projects/${project.id}/notifications`, { headers });
          if (!notifRes.ok) {
            return {
              projectId: project.id,
              zapierEnabled: false,
              reminderOffsetsDays: []
            };
          }
          const notifData = await notifRes.json();
          return {
            projectId: project.id,
            zapierEnabled: notifData.zapier_enabled === true,
            reminderOffsetsDays: notifData.reminder_offsets_days || []
          };
        } catch (error) {
          return {
            projectId: project.id,
            zapierEnabled: false,
            reminderOffsetsDays: []
          };
        }
      });

      const notificationStatuses = await Promise.all(notificationPromises);
      
      // Compute counts
      const withAlerts = notificationStatuses.filter(
        (status) => status.zapierEnabled && status.reminderOffsetsDays.length > 0
      );
      const needingSetup = notificationStatuses.filter(
        (status) => !status.zapierEnabled || status.reminderOffsetsDays.length === 0
      );
      
      setProjectsWithAlerts(withAlerts.length);
      setProjectsNeedingSetup(needingSetup.length);
      
      // Find first project needing setup
      const firstNeedingSetup = notificationStatuses.find(
        (status) => !status.zapierEnabled || status.reminderOffsetsDays.length === 0
      );
      setFirstProjectNeedingSetup(firstNeedingSetup?.projectId || null);
    } catch (error) {
      console.error('Error fetching projects notification status:', error);
    }
  };

  // Note: Zapier status is now fetched via usePlan hook, no separate fetch needed

  // Always route through your Zapier setup page (so you control UX + focus highlight)
  const QUICK_START_SLACK_URL = "/zapier?focus=slack";

  const handleQuickStart = () => {
    // Internal route → same tab
    if (QUICK_START_SLACK_URL.startsWith("/")) {
      window.location.href = QUICK_START_SLACK_URL;
      return;
    }

    // External → new tab
    window.open(QUICK_START_SLACK_URL, "_blank", "noopener,noreferrer");
  };

  const handleSetUpAlerts = () => {
    if (firstProjectNeedingSetup && onProjectExpand) {
      onProjectExpand(firstProjectNeedingSetup);
    } else {
      navigate('/zapier');
    }
  };

  const handleConnectZapier = () => {
    navigate('/zapier');
  };

  if (loading) {
    return (
      <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Zapier Automation</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading status...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            Zapier Automation
            {zapierConnected ? (
              <Badge className="bg-success text-success-foreground text-xs">
                ⚡ Connected
              </Badge>
            ) : (
              <Badge variant="outline" className="text-xs">
                ⚡ Not connected
              </Badge>
            )}
          </CardTitle>
        </div>
        
        {/* Meta lines */}
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground mt-2">
          <span>Last sync: {formatRelativeTime(lastStatusCheckAt)}</span>
          {zapierConnected && (
            <>
              <span>Alerts active for {projectsWithAlerts} {projectsWithAlerts === 1 ? 'project' : 'projects'}</span>
              <span>• {projectsNeedingSetup} {projectsNeedingSetup === 1 ? 'project' : 'projects'} need setup</span>
            </>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Locked State for Free/Basic Plan */}
        {isZapierLocked ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-4 bg-muted/50 rounded-lg border border-border">
              <Lock className="h-5 w-5 text-muted-foreground" />
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">
                  Zapier Automation is available on Automated plan
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Upgrade to Automated ($149/month) to unlock Zapier integrations with 6,000+ apps.
                </p>
              </div>
            </div>
            <Button
              size="default"
              onClick={() => setUpgradeModalOpen(true)}
              className="w-full bg-primary hover:bg-primary/90"
            >
              Upgrade to Unlock Zapier
            </Button>
          </div>
        ) : (
          <>
            {/* Alerts Status */}
            {zapierConnected && (
              <div>
                <h4 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-1">
                  <Bell className="h-4 w-4" />
                  Alerts Status
                </h4>
                <p className="text-sm text-muted-foreground">
                  {projectsWithAlerts} {projectsWithAlerts === 1 ? 'project' : 'projects'} with alerts • {projectsNeedingSetup} {projectsNeedingSetup === 1 ? 'project' : 'projects'} need setup
                </p>
              </div>
            )}

            {!zapierConnected && (
              <p className="text-sm text-muted-foreground">
                Connect Zapier to enable alerts for your projects.
              </p>
            )}

            {/* Action Buttons */}
            <TooltipProvider>
              <div className="flex flex-wrap gap-2 pt-2">
                {/* Primary Button - Dynamic based on state */}
                {!zapierConnected ? (
                  <Button
                    size="default"
                    onClick={handleConnectZapier}
                    className="bg-primary hover:bg-primary/90"
                  >
                    <Zap className="h-4 w-4 mr-2" />
                    Connect Zapier
                  </Button>
                ) : projectsNeedingSetup > 0 && firstProjectNeedingSetup ? (
                  <Button
                    size="default"
                    onClick={handleSetUpAlerts}
                    className="bg-primary hover:bg-primary/90"
                  >
                    <Bell className="h-4 w-4 mr-2" />
                    Set Up Alerts for {projectsNeedingSetup} {projectsNeedingSetup === 1 ? 'Project' : 'Projects'}
                  </Button>
                ) : (
                  <Button
                    size="default"
                    onClick={() => navigate('/zapier')}
                    className="bg-primary hover:bg-primary/90"
                  >
                    View All Alert Settings
                  </Button>
                )}

                {/* Quick Start Button - Always Visible as Secondary */}
                {!zapierConnected ? (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span>
                        <Button
                          variant="outline"
                          size="default"
                          disabled
                        >
                          <Rocket className="h-4 w-4 mr-2" />
                          Quick Start with Slack
                        </Button>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Connect Zapier first</p>
                    </TooltipContent>
                  </Tooltip>
                ) : (
                  <Button
                    variant="outline"
                    size="default"
                    onClick={handleQuickStart}
                  >
                    <Rocket className="h-4 w-4 mr-2" />
                    Quick Start with Slack
                  </Button>
                )}
              </div>
            </TooltipProvider>
          </>
        )}
      </CardContent>
      
      <UpgradeModal open={upgradeModalOpen} onOpenChange={setUpgradeModalOpen} />
    </Card>
  );
};

