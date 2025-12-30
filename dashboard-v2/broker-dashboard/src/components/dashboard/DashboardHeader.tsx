import { LogOut, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";

export const DashboardHeader = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");

  useEffect(() => {
    const storedEmail = localStorage.getItem("broker_email");
    if (storedEmail) {
      setEmail(storedEmail);
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("broker_token");
    localStorage.removeItem("broker_email");
    localStorage.removeItem("broker_name");
    navigate("/login");
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-card/95 backdrop-blur-sm card-shadow">
      <div className="container flex h-16 items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-sm">B</span>
            </div>
            <span className="text-lg font-bold text-foreground">Broker Dashboard</span>
          </div>
        </div>

        <nav className="flex items-center gap-6">
          <span className="text-sm text-muted-foreground hidden sm:block">{email}</span>
          <a
            href="/"
            className="flex items-center gap-1.5 text-sm font-medium text-foreground hover:text-primary transition-colors"
          >
            LienDeadline
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            className="text-destructive hover:text-destructive hover:bg-destructive/10"
          >
            <LogOut className="h-4 w-4 mr-1.5" />
            Logout
          </Button>
        </nav>
      </div>
    </header>
  );
};
