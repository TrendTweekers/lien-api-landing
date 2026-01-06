import { useState, useEffect } from "react";
import { Mail, Download, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { usePlan } from "@/hooks/usePlan";

interface EmailCapture {
  email: string;
  created_at: string;
  ip_address: string | null;
  last_used_at: string | null;
}

export const EmailCaptures = () => {
  const { planInfo } = usePlan();
  const [captures, setCaptures] = useState<EmailCapture[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCaptures = async () => {
    if (!planInfo.isAdmin) return;

    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('session_token');
      if (!token) {
        setError("Not authenticated");
        setLoading(false);
        return;
      }

      const res = await fetch('/api/admin/email-captures?limit=100', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!res.ok) {
        if (res.status === 403) {
          setError("Admin access required");
        } else {
          setError(`Failed to fetch: ${res.status}`);
        }
        setLoading(false);
        return;
      }

      const data = await res.json();
      setCaptures(data.captures || []);
    } catch (err) {
      console.error('Error fetching email captures:', err);
      setError("Failed to fetch email captures");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (planInfo.isAdmin) {
      fetchCaptures();
    }
  }, [planInfo.isAdmin]);

  const exportToCSV = () => {
    const headers = ['Email', 'Created At', 'IP Address', 'Last Used At'];
    const rows = captures.map(c => [
      c.email,
      c.created_at || '',
      c.ip_address || '',
      c.last_used_at || ''
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `email-captures-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  if (!planInfo.isAdmin) {
    return null;
  }

  return (
    <Card className="bg-card rounded-xl border border-border card-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Mail className="h-5 w-5 text-primary" />
            Email Captures
          </CardTitle>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchCaptures}
              disabled={loading}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={exportToCSV}
              disabled={captures.length === 0}
            >
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading email captures...</p>
        ) : error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : captures.length === 0 ? (
          <p className="text-sm text-muted-foreground">No email captures found.</p>
        ) : (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground mb-4">
              Showing {captures.length} most recent email captures
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-2 font-semibold">Email</th>
                    <th className="text-left py-2 px-2 font-semibold">Created</th>
                    <th className="text-left py-2 px-2 font-semibold">IP Address</th>
                    <th className="text-left py-2 px-2 font-semibold">Last Used</th>
                  </tr>
                </thead>
                <tbody>
                  {captures.map((capture, idx) => (
                    <tr key={idx} className="border-b border-border/50">
                      <td className="py-2 px-2">{capture.email}</td>
                      <td className="py-2 px-2 text-muted-foreground">
                        {capture.created_at ? new Date(capture.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="py-2 px-2 text-muted-foreground">
                        {capture.ip_address || '—'}
                      </td>
                      <td className="py-2 px-2 text-muted-foreground">
                        {capture.last_used_at ? new Date(capture.last_used_at).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

