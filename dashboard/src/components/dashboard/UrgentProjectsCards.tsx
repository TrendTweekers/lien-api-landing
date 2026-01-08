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
}

export const UrgentProjectsCards = () => {
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
        bgColor: 'bg-red-50',
        borderColor: 'border-red-200',
        badgeBg: 'bg-red-100',
        badgeText: 'text-red-700',
        progressBg: 'bg-red-500',
        daysColor: 'text-red-700'
      };
    } else {
      return {
        label: 'WARNING',
        bgColor: 'bg-yellow-50',
        borderColor: 'border-yellow-200',
        badgeBg: 'bg-yellow-100',
        badgeText: 'text-yellow-700',
        progressBg: 'bg-yellow-500',
        daysColor: 'text-yellow-700'
      };
    }
  };

  const getProgressPercent = (days: number) => {
    // Assume 90 days total, calculate what's left
    return Math.min(100, Math.max(0, (days / 90) * 100));
  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3].map(i => (
          <div key={i} className="bg-card rounded-xl p-6 border border-border card-shadow animate-pulse">
            <div className="h-32 bg-muted rounded"></div>
          </div>
        ))}
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
    <div>
      <div className="flex items-center gap-2 mb-6">
        <AlertTriangle className="h-5 w-5 text-red-600" />
        <h2 className="text-xl font-bold text-foreground">Urgent Deadlines</h2>
        <span className="text-sm text-muted-foreground">({urgentProjects.length} projects need attention)</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {urgentProjects.map((project: any) => {
          const status = getStatusConfig(project.daysRemaining);
          const progressPercent = getProgressPercent(project.daysRemaining);

          return (
            <div
              key={project.id}
              className={`rounded-xl border-2 p-6 ${status.bgColor} ${status.borderColor} hover:shadow-lg transition-all cursor-pointer`}
            >
              {/* Header */}
              <div className="flex justify-between items-start mb-4">
                <span className={`px-3 py-1 rounded-full text-xs font-bold ${status.badgeBg} ${status.badgeText}`}>
                  {status.label}
                </span>
                <span className={`text-sm font-bold ${status.daysColor}`}>
                  {project.daysRemaining} days
                </span>
              </div>

              {/* Project Name */}
              <h3 className="text-lg font-bold text-gray-900 mb-2 line-clamp-1">
                {project.project_name || 'Unnamed Project'}
              </h3>

              {/* Description */}
              <p className="text-sm text-gray-600 mb-1">
                Preliminary notice due {new Date(project.prelim_deadline).toLocaleDateString('en-US', { 
                  month: 'short', 
                  day: 'numeric',
                  year: 'numeric'
                })}
              </p>
              <p className="text-xs text-gray-500 mb-4">
                {project.state} • {project.client_name || 'Client'}
              </p>

              {/* Progress Bar */}
              <div className="relative">
                <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
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

