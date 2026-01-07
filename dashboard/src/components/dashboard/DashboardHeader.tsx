import { LogOut, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useEffect, useState } from "react";

export const DashboardHeader = () => {
  const [userEmail, setUserEmail] = useState<string>("");

  useEffect(() => {
    // Get user email from localStorage or fetch from API
    const storedEmail = localStorage.getItem('user_email') || localStorage.getItem('userEmail');
    if (storedEmail) {
      setUserEmail(storedEmail);
    } else {
      // Try to get from API
      const token = localStorage.getItem('session_token');
      if (token) {
        fetch('/api/verify-session', {
          headers: { 'Authorization': `Bearer ${token}` }
        })
          .then(res => res.json())
          .then(data => {
            if (data.email) {
              setUserEmail(data.email);
              localStorage.setItem('user_email', data.email);
            }
          })
          .catch(() => {
            // Fallback to stored email if API fails
            const fallback = localStorage.getItem('user_email') || localStorage.getItem('userEmail');
            if (fallback) setUserEmail(fallback);
          });
      }
    }
  }, []);

  const handleLogout = async () => {
    try {
      // Call logout API endpoint if it exists (optional - for server-side session clearing)
      const token = localStorage.getItem('session_token');
      if (token) {
        try {
          await fetch('/api/logout', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          });
        } catch (error) {
          // If logout endpoint doesn't exist, that's okay - we'll still clear client-side
          console.log('Logout endpoint not available, clearing client-side only');
        }
      }
      
      // Clear all localStorage items related to session
      localStorage.removeItem('session_token');
      localStorage.removeItem('user_email');
      localStorage.removeItem('userEmail');
      localStorage.removeItem('loginTime');
      
      // Clear any cookies that might be set
      document.cookie.split(";").forEach((c) => {
        document.cookie = c
          .replace(/^ +/, "")
          .replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/");
      });
      
      // Redirect to login page
      window.location.href = '/login.html';
    } catch (error) {
      console.error('Logout error:', error);
      // Even if there's an error, clear localStorage and redirect
      localStorage.clear();
      window.location.href = '/login.html';
    }
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-card/95 backdrop-blur-sm card-shadow">
      <div className="container flex h-16 items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-sm">L</span>
            </div>
            <span className="text-lg font-bold text-foreground">LienDeadline</span>
          </div>
        </div>

        <nav className="flex items-center gap-6">
          <span className="text-sm text-muted-foreground hidden sm:block">{userEmail || "Loading..."}</span>
          <a
            href="/"
            className="flex items-center gap-1.5 text-sm font-medium text-foreground hover:text-primary transition-colors"
          >
            Landing Page
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
          <Button
            variant="ghost"
            size="sm"
            className="text-destructive hover:text-destructive hover:bg-destructive/10"
            onClick={handleLogout}
          >
            <LogOut className="h-4 w-4 mr-1.5" />
            Logout
          </Button>
        </nav>
      </div>
    </header>
  );
};
