import { useState, useEffect } from "react";
import { AlertTriangle, Clock } from "lucide-react";

interface Project {
  id: number;
  project_name: string;
  client_name: string;
  state: string;
  prelim_deadline: string;
  lien_deadline: string;
  created_at: string;
  daysRemaining?: number;
}

interface UrgentProjectsCardsProps {
  onProjectClick?: (projectId: number) => void;
}

export const UrgentProjectsCards = ({ onProjectClick }: UrgentProjectsCardsProps) => {
  const [urgentProjects, setUrgentProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('session_token');
    fetch("/api/calculations/history", {
      headers: { "Authorization": `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        const projects = Array.isArray(data.history) ? data.history : [];
        
        // Calculate days remaining and filter urgent/warning projects
        const now = new Date();
        const projectsWithDays = projects.map(p => {
          const prelimDate = new Date(p.prelim_deadline);
          const daysRemaining = Math.ceil((prelimDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
          return { ...p, daysRemaining };
        });

        // Filter to only urgent (≤7 days) and warning (8-30 days)
        const filtered = projectsWithDays
          .filter(p => p.daysRemaining <= 30)
          .sort((a, b) => a.daysRemaining - b.daysRemaining)
          .slice(0, 6); // Show max 6 cards

        setUrgentProjects(filtered);
        setLoading(false);
      })
      .catch(err => {
        console.error('Error fetching projects:', err);
        setLoading(false);
      });
  }, []);

  const getStatusConfig = (days: number) => {
    if (days <= 7) {
      return {
        label: 'CRITICAL',
        badgeBg: 'bg-red-100',
        badgeText: 'text-red-700',
        daysBg: 'bg-red-50',
        daysText: 'text-red-700',
        progressBg: 'bg-red-500'
      };
    } else {
      return {
        label: 'WARNING',
        badgeBg: 'bg-yellow-100',
        badgeText: 'text-yellow-700',
        daysBg: 'bg-yellow-50',
        daysText: 'text-yellow-700',
        progressBg: 'bg-yellow-500'
      };
    }
  };

  const getProgressPercent = (days: number) => {
    // Assume 90 days total, calculate what's left
    return Math.min(100, Math.max(0, (days / 90) * 100));
  };

  const handleCardClick = (projectId: number) => {
    // Scroll to projects table
    const projectsSection = document.querySelector('[data-projects-section]');
    if (projectsSection) {
      projectsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    // Call parent callback to expand project row
    if (onProjectClick) {
      onProjectClick(projectId);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <div className="h-6 w-6 bg-muted rounded animate-pulse"></div>
          <div className="h-6 w-48 bg-muted rounded animate-pulse"></div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-card rounded-xl p-6 border border-border animate-pulse">
              <div className="h-32 bg-muted rounded"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (urgentProjects.length === 0) {
    return (
      <div className="bg-green-50 border-2 border-green-200 rounded-xl p-8 text-center">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Clock className="h-8 w-8 text-green-600" />
        </div>
        <h3 className="text-lg font-semibold text-green-900 mb-2">All Clear!</h3>
        <p className="text-sm text-green-700">No urgent deadlines in the next 30 days.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-5 w-5 text-red-600" />
        <h2 className="text-xl font-bold text-foreground">Urgent Deadlines</h2>
        <span className="text-sm text-muted-foreground">({urgentProjects.length} project{urgentProjects.length !== 1 ? 's' : ''} need attention)</span>
      </div>

      {/* Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {urgentProjects.map((project) => {
          const status = getStatusConfig(project.daysRemaining!);
          const progressPercent = getProgressPercent(project.daysRemaining!);

          return (
            <div
              key={project.id}
              onClick={() => handleCardClick(project.id)}
              className="bg-card rounded-xl border-2 border-border p-6 hover:shadow-lg hover:border-primary/30 transition-all cursor-pointer"
            >
              {/* Header with badges */}
              <div className="flex justify-between items-start mb-4">
                <span className={`px-3 py-1 rounded-md text-xs font-bold ${status.badgeBg} ${status.badgeText}`}>
                  {status.label}
                </span>
                <span className={`px-3 py-1 rounded-md text-sm font-bold ${status.daysBg} ${status.daysText}`}>
                  {project.daysRemaining} days
                </span>
              </div>

              {/* Project Name */}
              <h3 className="text-lg font-bold text-foreground mb-2 line-clamp-1">
                {project.project_name || 'Unnamed Project'}
              </h3>

              {/* Description */}
              <p className="text-sm text-muted-foreground mb-1">
                Preliminary notice due {new Date(project.prelim_deadline).toLocaleDateString('en-US', { 
                  month: 'short', 
                  day: 'numeric',
                  year: 'numeric'
                })}
              </p>
              <p className="text-xs text-muted-foreground mb-4">
                {project.state} {project.client_name ? `• ${project.client_name}` : ''}
              </p>

              {/* Progress Bar */}
              <div className="relative">
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all ${status.progressBg}`}
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
