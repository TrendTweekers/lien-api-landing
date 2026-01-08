import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Mail, Zap, Calendar, Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";

interface NotificationModalProps {
  project: any;
  isOpen: boolean;
  onClose: () => void;
  userTier: string;
}

export const NotificationModal = ({ project, isOpen, onClose, userTier }: NotificationModalProps) => {
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [emailReminderDays, setEmailReminderDays] = useState({ day1: true, day7: true, day14: false });
  const [zapierEnabled, setZapierEnabled] = useState(false);
  const [zapierReminderDays, setZapierReminderDays] = useState({ day1: true, day7: true, day14: false });
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
          // Email settings
          setEmailEnabled(data.email_enabled || false);
          const emailDays = data.email_reminder_offsets_days || [1, 7];
          setEmailReminderDays({
            day1: emailDays.includes(1),
            day7: emailDays.includes(7),
            day14: emailDays.includes(14)
          });
          
          // Zapier settings
          setZapierEnabled(data.zapier_enabled || false);
          const zapierDays = data.zapier_reminder_offsets_days || [1, 7];
          setZapierReminderDays({
            day1: zapierDays.includes(1),
            day7: zapierDays.includes(7),
            day14: zapierDays.includes(14)
          });
        })
        .catch(err => console.error('Error:', err));
    }
  }, [isOpen, project]);

  const handleSave = async () => {
    setSaving(true);
    
    // Build email reminder days array
    const emailDays = [];
    if (emailReminderDays.day1) emailDays.push(1);
    if (emailReminderDays.day7) emailDays.push(7);
    if (emailReminderDays.day14) emailDays.push(14);

    // Build zapier reminder days array
    const zapierDays = [];
    if (zapierReminderDays.day1) zapierDays.push(1);
    if (zapierReminderDays.day7) zapierDays.push(7);
    if (zapierReminderDays.day14) zapierDays.push(14);

    try {
      const token = localStorage.getItem('session_token');
      const response = await fetch(`/api/projects/${project.id}/notifications`, {
        method: 'PUT',
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          email_enabled: emailEnabled,
          email_reminder_offsets_days: emailDays,
          zapier_enabled: zapierEnabled,
          zapier_reminder_offsets_days: zapierDays
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
          <DialogTitle>Configure Notifications - {project.project_name || 'Unnamed Project'}</DialogTitle>
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

        {/* Email Reminders - Per Project */}
        <div className="border-2 border-blue-200 bg-blue-50 rounded-lg p-4 mb-4">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-start gap-3">
              <Mail className="h-5 w-5 text-blue-600 mt-1" />
              <div>
                <h4 className="font-semibold mb-1">Email Reminders</h4>
                <p className="text-sm text-gray-600">
                  {userTier === 'free' ? 'Available on Basic plan' : 'Configure for this project'}
                </p>
              </div>
            </div>
            
            {/* Toggle - Only if Basic+ */}
            {userTier !== 'free' && (
              <button
                onClick={() => setEmailEnabled(!emailEnabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  emailEnabled ? 'bg-blue-500' : 'bg-gray-300'
                }`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  emailEnabled ? 'translate-x-6' : 'translate-x-1'
                }`} />
              </button>
            )}
          </div>

          {/* Schedule Selection */}
          {userTier !== 'free' && emailEnabled && (
            <div className="ml-8 space-y-2">
              <p className="text-sm font-medium mb-2">Reminder Schedule:</p>
              
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={emailReminderDays.day1} 
                  onChange={(e) => setEmailReminderDays({...emailReminderDays, day1: e.target.checked})}
                  className="w-4 h-4 text-blue-500 rounded" />
                <span className="text-sm">1 day before deadline</span>
              </label>
              
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={emailReminderDays.day7}
                  onChange={(e) => setEmailReminderDays({...emailReminderDays, day7: e.target.checked})}
                  className="w-4 h-4 text-blue-500 rounded" />
                <span className="text-sm">7 days before deadline</span>
              </label>
              
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={emailReminderDays.day14}
                  onChange={(e) => setEmailReminderDays({...emailReminderDays, day14: e.target.checked})}
                  className="w-4 h-4 text-blue-500 rounded" />
                <span className="text-sm">14 days before deadline</span>
              </label>
            </div>
          )}

          {userTier === 'free' && (
            <p className="text-xs text-blue-700 mt-3 ml-8">
              Upgrade to Basic ($49/mo) to enable email reminders
            </p>
          )}
        </div>

        {/* Zapier Automation - Per Project */}
        {(userTier === 'automated' || userTier === 'enterprise') && (
          <div className="border-2 border-orange-200 bg-orange-50 rounded-lg p-4">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-start gap-3">
                <Zap className="h-5 w-5 text-orange-600 mt-1" />
                <div>
                  <h4 className="font-semibold">Zapier Automation</h4>
                  <p className="text-sm text-gray-600">Configure for this project</p>
                </div>
              </div>
              
              {/* Toggle */}
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
                  <input type="checkbox" checked={zapierReminderDays.day1} 
                    onChange={(e) => setZapierReminderDays({...zapierReminderDays, day1: e.target.checked})}
                    className="w-4 h-4 text-orange-500 rounded" />
                  <span className="text-sm">1 day before deadline</span>
                </label>
                
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={zapierReminderDays.day7}
                    onChange={(e) => setZapierReminderDays({...zapierReminderDays, day7: e.target.checked})}
                    className="w-4 h-4 text-orange-500 rounded" />
                  <span className="text-sm">7 days before deadline</span>
                </label>
                
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={zapierReminderDays.day14}
                    onChange={(e) => setZapierReminderDays({...zapierReminderDays, day14: e.target.checked})}
                    className="w-4 h-4 text-orange-500 rounded" />
                  <span className="text-sm">14 days before deadline</span>
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
            disabled={saving || userTier === 'free'} 
            className="flex-1 bg-orange-500 hover:bg-orange-600 text-white"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
