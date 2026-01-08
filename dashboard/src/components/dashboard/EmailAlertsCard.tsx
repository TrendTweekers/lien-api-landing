import { useState, useEffect } from "react";
import { Mail, Check, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

export const EmailAlertsCard = () => {
  const [emails, setEmails] = useState("");
  const [savedEmails, setSavedEmails] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  useEffect(() => {
    // Fetch current email preferences
    const token = localStorage.getItem('session_token');
    fetch("/api/user/preferences", {
      headers: { "Authorization": `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        const notificationEmails = data.notification_emails || "";
        setEmails(notificationEmails);
        setSavedEmails(notificationEmails);
        setLoading(false);
      })
      .catch(err => {
        console.error('Error fetching email preferences:', err);
        setLoading(false);
      });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);

    // Basic email validation
    const emailList = emails.split(',').map(e => e.trim()).filter(e => e);
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const invalidEmails = emailList.filter(e => !emailRegex.test(e));

    if (invalidEmails.length > 0) {
      setMessage({ type: 'error', text: `Invalid email(s): ${invalidEmails.join(', ')}` });
      setSaving(false);
      return;
    }

    try {
      const token = localStorage.getItem('session_token');
      const response = await fetch("/api/user/preferences", {
        method: 'POST',
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          notification_emails: emails
        })
      });

      if (response.ok) {
        setSavedEmails(emails);
        setMessage({ type: 'success', text: 'Email addresses saved successfully!' });
        setTimeout(() => setMessage(null), 3000);
        // Dispatch event so NotificationModal can refresh
        window.dispatchEvent(new Event('notification-emails-updated'));
      } else {
        setMessage({ type: 'error', text: 'Failed to save email addresses. Please try again.' });
      }
    } catch (error) {
      console.error('Error saving emails:', error);
      setMessage({ type: 'error', text: 'Error saving email addresses.' });
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = emails.trim() !== savedEmails.trim();

  if (loading) {
    return (
      <div className="bg-card rounded-xl border-2 border-border p-6 animate-pulse">
        <div className="h-6 bg-muted rounded w-48 mb-4"></div>
        <div className="h-20 bg-muted rounded"></div>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-xl border-2 border-border p-6">
      {/* Header */}
      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center shrink-0">
          <Mail className="h-5 w-5 text-blue-600" />
        </div>
        <div className="flex-1">
          <h3 className="text-xl font-bold text-foreground mb-1">Email Alerts</h3>
          <p className="text-sm text-muted-foreground">
            Enter the email address(es) where you want to receive deadline notifications. 
            You can add multiple emails separated by commas.
          </p>
        </div>
      </div>

      {/* Email Input */}
      <div className="space-y-4">
        <div>
          <label htmlFor="notification-emails" className="block text-sm font-medium text-foreground mb-2">
            Notification Email Addresses
          </label>
          <input
            id="notification-emails"
            type="text"
            value={emails}
            onChange={(e) => setEmails(e.target.value)}
            placeholder="example@company.com, manager@company.com"
            className="w-full px-4 py-3 border-2 border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
          />
          <p className="text-xs text-muted-foreground mt-2">
            💡 Tip: Separate multiple emails with commas
          </p>
        </div>

        {/* Info Box */}
        <div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-4">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-5 w-5 text-blue-600 shrink-0 mt-0.5" />
            <div className="text-sm text-blue-800">
              <p className="font-semibold mb-1">How it works:</p>
              <ul className="space-y-1 list-disc list-inside">
                <li>These emails will receive alerts from projects you enable</li>
                <li>Configure which projects send alerts by clicking on project cards below</li>
                <li>Each project can have custom reminder schedules (1, 7, or 14 days before deadlines)</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div className="flex items-center gap-3">
          <Button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-3 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Saving...
              </>
            ) : (
              <>
                <Mail className="h-4 w-4 mr-2" />
                Save Email Addresses
              </>
            )}
          </Button>

          {/* Success/Error Message */}
          {message && (
            <div className={`flex items-center gap-2 text-sm font-medium ${
              message.type === 'success' ? 'text-green-600' : 'text-red-600'
            }`}>
              {message.type === 'success' ? (
                <Check className="h-4 w-4" />
              ) : (
                <AlertCircle className="h-4 w-4" />
              )}
              {message.text}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
