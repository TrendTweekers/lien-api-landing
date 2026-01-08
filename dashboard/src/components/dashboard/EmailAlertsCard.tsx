import { useState, useEffect } from "react";
import { Mail, Check, AlertCircle, X, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

export const EmailAlertsCard = () => {
  const [emailList, setEmailList] = useState<string[]>([]);
  const [newEmail, setNewEmail] = useState("");
  const [savedEmails, setSavedEmails] = useState<string[]>([]);
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
        const emailsArray = notificationEmails
          .split(',')
          .map(e => e.trim())
          .filter(e => e);
        setEmailList(emailsArray);
        setSavedEmails(emailsArray);
        setLoading(false);
      })
      .catch(err => {
        console.error('Error fetching email preferences:', err);
        setLoading(false);
      });
  }, []);

  const handleAddEmail = () => {
    const trimmedEmail = newEmail.trim();
    if (!trimmedEmail) return;

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedEmail)) {
      setMessage({ type: 'error', text: `Invalid email: ${trimmedEmail}` });
      setTimeout(() => setMessage(null), 3000);
      return;
    }

    if (emailList.includes(trimmedEmail)) {
      setMessage({ type: 'error', text: 'This email is already added.' });
      setTimeout(() => setMessage(null), 3000);
      return;
    }

    const updatedList = [...emailList, trimmedEmail];
    setEmailList(updatedList);
    setNewEmail("");
    handleSave(updatedList);
  };

  const handleRemoveEmail = (emailToRemove: string) => {
    const updatedList = emailList.filter(e => e !== emailToRemove);
    setEmailList(updatedList);
    handleSave(updatedList);
  };

  const handleSave = async (emailsToSave?: string[]) => {
    const emailsToSaveList = emailsToSave || emailList;
    setSaving(true);
    setMessage(null);

    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const invalidEmails = emailsToSaveList.filter(e => !emailRegex.test(e));

    if (invalidEmails.length > 0) {
      setMessage({ type: 'error', text: `Invalid email(s): ${invalidEmails.join(', ')}` });
      setSaving(false);
      return;
    }

    try {
      const token = localStorage.getItem('session_token');
      const notificationEmailsString = emailsToSaveList.join(', ');
      const response = await fetch("/api/user/preferences", {
        method: 'POST',
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          notification_emails: notificationEmailsString
        })
      });

      if (response.ok) {
        setSavedEmails(emailsToSaveList);
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

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddEmail();
    }
  };

  const hasChanges = JSON.stringify(emailList.sort()) !== JSON.stringify(savedEmails.sort());

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

      {/* Email Management */}
      <div className="space-y-4">
        {/* Saved Email Chips */}
        {emailList.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Saved Email Addresses ({emailList.length})
            </label>
            <div className="flex flex-wrap gap-2 mb-3">
              {emailList.map((email, index) => (
                <div
                  key={index}
                  className="inline-flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-lg px-3 py-1.5 text-sm"
                >
                  <Mail className="h-3 w-3 text-blue-600" />
                  <span className="text-blue-900 font-medium">{email}</span>
                  <button
                    onClick={() => handleRemoveEmail(email)}
                    className="ml-1 hover:bg-blue-200 rounded-full p-0.5 transition-colors"
                    title="Remove email"
                  >
                    <X className="h-3 w-3 text-blue-600" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Add New Email */}
        <div>
          <label htmlFor="new-email" className="block text-sm font-medium text-foreground mb-2">
            {emailList.length === 0 ? 'Add Email Addresses' : 'Add Another Email'}
          </label>
          <div className="flex gap-2">
            <input
              id="new-email"
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="example@company.com"
              className="flex-1 px-4 py-3 border-2 border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
            />
            <Button
              onClick={handleAddEmail}
              disabled={!newEmail.trim() || saving}
              className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-3 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            💡 Press Enter or click the + button to add an email
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

        {/* Manual Save Button (if needed) */}
        {hasChanges && (
          <div className="flex items-center gap-3">
            <Button
              onClick={() => handleSave()}
              disabled={saving}
              className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-3 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Saving...
                </>
              ) : (
                <>
                  <Check className="h-4 w-4 mr-2" />
                  Save Changes
                </>
              )}
            </Button>
          </div>
        )}

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
  );
};
