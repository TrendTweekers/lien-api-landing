import { useState, useEffect } from "react";
import { X, Mail, Zap, Calendar, Bell } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Project {
  id: number;
  project_name: string;
  client_name: string;
  state: string;
  prelim_deadline: string;
  lien_deadline: string;
  amount?: number;
}

interface NotificationModalProps {
  project: Project;
  isOpen: boolean;
  onClose: () => void;
  userTier: 'free' | 'basic' | 'automated' | 'enterprise';
}

export const NotificationModal = ({ 
  project, 
  isOpen, 
  onClose,
  userTier 
}: NotificationModalProps) => {
  const [zapierEnabled, setZapierEnabled] = useState(false);
  const [reminderDays, setReminderDays] = useState({
    day1: true,
    day7: true,
    day14: false
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      // Fetch current notification settings for this project
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
        .catch(err => console.error('Error fetching notifications:', err));
    }
  }, [isOpen, project.id]);

  const handleSave = async () => {
    setSaving(true);
    
    // Build reminder days array
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
        alert('Notification settings saved!');
        onClose();
      } else {
        alert('Failed to save settings. Please try again.');
      }
    } catch (error) {
      console.error('Error saving notifications:', error);
      alert('Error saving settings');
    } finally {
      setSaving(false);
    }
  };

  const calculateDaysRemaining = (deadline: string) => {
    const now = new Date();
    const deadlineDate = new Date(deadline);
    return Math.ceil((deadlineDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  };

  const prelimDays = calculateDaysRemaining(project.prelim_deadline);
  const lienDays = calculateDaysRemaining(project.lien_deadline);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center rounded-t-2xl">
          <h2 className="text-2xl font-bold text-gray-900">Configure Notifications</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-6 space-y-6">
          {/* Project Info */}
          <div className="bg-gray-50 rounded-xl p-4">
            <h3 className="text-lg font-bold text-gray-900 mb-2">
              {project.project_name || 'Unnamed Project'}
            </h3>
            <p className="text-sm text-gray-600 mb-3">
              {project.client_name} • {project.state}
              {project.amount && ` • $${project.amount.toLocaleString()}`}
            </p>
            
            {/* Deadlines */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-gray-500" />
                <span className="text-sm text-gray-700">
                  <strong>Prelim Notice:</strong> {new Date(project.prelim_deadline).toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric',
                    year: 'numeric'
                  })}
                  <span className={`ml-2 font-semibold ${prelimDays <= 7 ? 'text-red-600' : prelimDays <= 30 ? 'text-yellow-600' : 'text-green-600'}`}>
                    ({prelimDays} days)
                  </span>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-gray-500" />
                <span className="text-sm text-gray-700">
                  <strong>Lien Filing:</strong> {new Date(project.lien_deadline).toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric',
                    year: 'numeric'
                  })}
                  <span className={`ml-2 font-semibold ${lienDays <= 7 ? 'text-red-600' : lienDays <= 30 ? 'text-yellow-600' : 'text-green-600'}`}>
                    ({lienDays} days)
                  </span>
                </span>
              </div>
            </div>
          </div>

          {/* Email Alerts (Global) */}
          <div className="border-2 border-blue-200 bg-blue-50 rounded-xl p-4">
            <div className="flex items-start gap-3 mb-3">
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center shrink-0">
                <Mail className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Email Reminders (Global)</h4>
                <p className="text-sm text-gray-600">
                  {userTier === 'free' 
                    ? 'Available on Basic plan and above'
                    : 'Enabled for all your projects'
                  }
                </p>
              </div>
            </div>
            
            {userTier !== 'free' && (
              <div className="ml-13 space-y-2">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 bg-blue-600 rounded flex items-center justify-center">
                    <span className="text-white text-xs">✓</span>
                  </div>
                  <span className="text-sm text-gray-700">7 days before deadline</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 bg-blue-600 rounded flex items-center justify-center">
                    <span className="text-white text-xs">✓</span>
                  </div>
                  <span className="text-sm text-gray-700">1 day before deadline</span>
                </div>
              </div>
            )}

            {userTier === 'free' && (
              <p className="text-xs text-blue-700 mt-3 ml-13">
                Upgrade to Basic ($49/mo) to enable email reminders
              </p>
            )}
          </div>

          {/* Zapier Automation (Automated Tier Only) */}
          {(userTier === 'automated' || userTier === 'enterprise') && (
            <div className="border-2 border-orange-200 bg-orange-50 rounded-xl p-4">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center shrink-0">
                    <Zap className="h-5 w-5 text-orange-600" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-900 mb-1">Zapier Automation</h4>
                    <p className="text-sm text-gray-600">Configure alerts for this project</p>
                  </div>
                </div>
                
                {/* Toggle */}
                <button
                  onClick={() => setZapierEnabled(!zapierEnabled)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    zapierEnabled ? 'bg-orange-500' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      zapierEnabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>

              {zapierEnabled && (
                <div className="ml-13 space-y-3">
                  <p className="text-sm font-medium text-gray-700 mb-2">Reminder Schedule:</p>
                  
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={reminderDays.day1}
                      onChange={(e) => setReminderDays({...reminderDays, day1: e.target.checked})}
                      className="w-5 h-5 text-orange-500 rounded border-gray-300 focus:ring-orange-500"
                    />
                    <span className="text-sm text-gray-700">1 day before deadline</span>
                  </label>
                  
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={reminderDays.day7}
                      onChange={(e) => setReminderDays({...reminderDays, day7: e.target.checked})}
                      className="w-5 h-5 text-orange-500 rounded border-gray-300 focus:ring-orange-500"
                    />
                    <span className="text-sm text-gray-700">7 days before deadline</span>
                  </label>
                  
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={reminderDays.day14}
                      onChange={(e) => setReminderDays({...reminderDays, day14: e.target.checked})}
                      className="w-5 h-5 text-orange-500 rounded border-gray-300 focus:ring-orange-500"
                    />
                    <span className="text-sm text-gray-700">14 days before deadline</span>
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
            <div className="bg-gradient-to-br from-orange-50 to-orange-100 border-2 border-orange-200 rounded-xl p-4">
              <div className="flex items-start gap-3">
                <Zap className="h-6 w-6 text-orange-600 shrink-0" />
                <div>
                  <h4 className="font-semibold text-gray-900 mb-2">Unlock Zapier Automation</h4>
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
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-white border-t border-gray-200 px-6 py-4 flex gap-3 rounded-b-2xl">
          <Button
            onClick={onClose}
            variant="outline"
            className="flex-1"
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            className="flex-1 bg-orange-500 hover:bg-orange-600 text-white"
            disabled={saving || (userTier !== 'automated' && userTier !== 'enterprise')}
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </Button>
        </div>
      </div>
    </div>
  );
};

