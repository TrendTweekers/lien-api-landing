import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { X, Mail, Zap, Calendar, Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";

interface NotificationModalProps {
  project: any;
  isOpen: boolean;
  onClose: () => void;
  userTier: string;
}

export const NotificationModal = ({ project, isOpen, onClose, userTier }: NotificationModalProps) => {
  const [zapierEnabled, setZapierEnabled] = useState(false);
  const [reminderDays, setReminderDays] = useState({ day1: true, day7: true, day14: false });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen && project) {
      // Fetch current settings
      const token = localStorage.getItem('session_token');
      fetch(`/api/projects/${project.id}/notifications`, {
        headers: { "Authorization": `Bearer ${token}` }
      })
        .then(r => r.json())
        .then(data => {
          setZapierEnabled(data.zapier_enabled || false);
          const days = data.reminder_offsets_days || [1, 7];
          setReminderDays({
            day1: days.includes(1),
            day7: days.includes(7),
            day14: days.includes(14)
          });
        })
        .catch(err => console.error('Error:', err));
    }
  }, [isOpen, project]);

  const handleSave = async () => {
    setSaving(true);
    const days = [];
    if (reminderDays.day1) days.push(1);
    if (reminderDays.day7) days.push(7);
    if (reminderDays.day14) days.push(14);

    try {
      const token = localStorage.getItem('session_token');
      const response = await fetch(`/api/projects/${project.id}/notifications`, {
        method: 'PUT',
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          zapier_enabled: zapierEnabled,
          reminder_offsets_days: days
        })
      });

      if (response.ok) {
        alert('Settings saved!');
        onClose();
      } else {
        alert('Failed to save');
      }
    } catch (error) {
      alert('Error saving');
    } finally {
      setSaving(false);
    }
  };

  if (!project) return null;

  const prelimDays = Math.ceil((new Date(project.prelim_deadline).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));
  const lienDays = Math.ceil((new Date(project.lien_deadline).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Configure Notifications</DialogTitle>
        </DialogHeader>

        {/* Project Info */}
        <div className="bg-gray-50 rounded-lg p-4 mb-4">
          <h3 className="font-bold text-lg mb-2">{project.project_name || 'Unnamed Project'}</h3>
          <p className="text-sm text-gray-600 mb-3">
            {project.client_name} • {project.state}
            {project.amount && ` • $${project.amount.toLocaleString()}`}
          </p>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              <span>
                Prelim: {new Date(project.prelim_deadline).toLocaleDateString()} 
                <span className={`ml-2 font-semibold ${prelimDays <= 7 ? 'text-red-600' : prelimDays <= 30 ? 'text-yellow-600' : 'text-green-600'}`}>
                  ({prelimDays} days)
                </span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              <span>
                Lien: {new Date(project.lien_deadline).toLocaleDateString()} 
                <span className={`ml-2 font-semibold ${lienDays <= 7 ? 'text-red-600' : lienDays <= 30 ? 'text-yellow-600' : 'text-green-600'}`}>
                  ({lienDays} days)
                </span>
              </span>
            </div>
          </div>
        </div>

        {/* Email Alerts */}
        <div className="border-2 border-blue-200 bg-blue-50 rounded-lg p-4 mb-4">
          <div className="flex items-start gap-3">
            <Mail className="h-5 w-5 text-blue-600 mt-1" />
            <div>
              <h4 className="font-semibold mb-1">Email Reminders (Global)</h4>
              <p className="text-sm text-gray-600">
                {userTier === 'free' ? 'Available on Basic plan' : 'Enabled for all projects'}
              </p>
              {userTier !== 'free' && (
                <div className="mt-2 space-y-1 text-sm">
                  <div>✓ 7 days before deadline</div>
                  <div>✓ 1 day before deadline</div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Zapier */}
        {(userTier === 'automated' || userTier === 'enterprise') && (
          <div className="border-2 border-orange-200 bg-orange-50 rounded-lg p-4">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-start gap-3">
                <Zap className="h-5 w-5 text-orange-600 mt-1" />
                <div>
                  <h4 className="font-semibold">Zapier Automation</h4>
                  <p className="text-sm text-gray-600">For this project</p>
                </div>
              </div>
              <button
                onClick={() => setZapierEnabled(!zapierEnabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  zapierEnabled ? 'bg-orange-500' : 'bg-gray-300'
                }`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  zapierEnabled ? 'translate-x-6' : 'translate-x-1'
                }`} />
              </button>
            </div>

            {zapierEnabled && (
              <div className="ml-8 space-y-2">
                <p className="text-sm font-medium mb-2">Reminder Schedule:</p>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={reminderDays.day1} 
                    onChange={(e) => setReminderDays({...reminderDays, day1: e.target.checked})}
                    className="w-4 h-4 text-orange-500 rounded" />
                  <span className="text-sm">1 day before</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={reminderDays.day7}
                    onChange={(e) => setReminderDays({...reminderDays, day7: e.target.checked})}
                    className="w-4 h-4 text-orange-500 rounded" />
                  <span className="text-sm">7 days before</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={reminderDays.day14}
                    onChange={(e) => setReminderDays({...reminderDays, day14: e.target.checked})}
                    className="w-4 h-4 text-orange-500 rounded" />
                  <span className="text-sm">14 days before</span>
                </label>
                <div className="bg-orange-100 border border-orange-200 rounded-lg p-3 mt-4">
                  <div className="flex items-start gap-2">
                    <Bell className="h-4 w-4 text-orange-600 mt-0.5 shrink-0" />
                    <p className="text-xs text-orange-800">
                      Alerts will be sent via your connected Zapier integrations (Slack, Calendar, Email, etc.)
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Upgrade CTA for Basic Tier */}
        {userTier === 'basic' && (
          <div className="bg-gradient-to-br from-orange-50 to-orange-100 border-2 border-orange-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Zap className="h-6 w-6 text-orange-600 shrink-0" />
              <div>
                <h4 className="font-semibold mb-2">Unlock Zapier Automation</h4>
                <p className="text-sm text-gray-700 mb-3">
                  Upgrade to Automated tier to send alerts to Slack, Calendar, SMS, and 6,000+ other apps.
                </p>
                <Button className="bg-orange-500 hover:bg-orange-600 text-white">
                  Upgrade to Automated ($149/mo)
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex gap-3 pt-4">
          <Button onClick={onClose} variant="outline" className="flex-1" disabled={saving}>
            Cancel
          </Button>
          <Button 
            onClick={handleSave} 
            disabled={saving || (userTier !== 'automated' && userTier !== 'enterprise')} 
            className="flex-1 bg-orange-500 hover:bg-orange-600 text-white"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
