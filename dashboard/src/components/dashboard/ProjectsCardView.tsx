import { useState } from "react";
import { Calendar, DollarSign, MapPin } from "lucide-react";
import { NotificationModal } from "./NotificationModal";

interface Project {
  id: number;
  project_name: string;
  client_name: string;
  state: string;
  prelim_deadline: string;
  lien_deadline: string;
  amount: number;
  invoice_date: string;
  created_at: string;
}

interface ProjectsCardViewProps {
  projects: Project[];
  userTier: 'free' | 'basic' | 'automated' | 'enterprise';
}

export const ProjectsCardView = ({ projects, userTier }: ProjectsCardViewProps) => {
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const calculateDaysRemaining = (deadline: string) => {
    const now = new Date();
    const deadlineDate = new Date(deadline);
    return Math.ceil((deadlineDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  };

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
    } else if (days <= 30) {
      return {
        label: 'WARNING',
        badgeBg: 'bg-yellow-100',
        badgeText: 'text-yellow-700',
        daysBg: 'bg-yellow-50',
        daysText: 'text-yellow-700',
        progressBg: 'bg-yellow-500'
      };
    } else {
      return {
        label: 'ON TRACK',
        badgeBg: 'bg-green-100',
        badgeText: 'text-green-700',
        daysBg: 'bg-green-50',
        daysText: 'text-green-700',
        progressBg: 'bg-green-500'
      };
    }
  };

  const getProgressPercent = (days: number) => {
    return Math.min(100, Math.max(0, (days / 90) * 100));
  };

  const handleCardClick = (project: Project) => {
    setSelectedProject(project);
    setModalOpen(true);
  };

  if (projects.length === 0) {
    return (
      <div className="bg-gray-50 border-2 border-gray-200 rounded-xl p-12 text-center">
        <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Calendar className="h-10 w-10 text-gray-400" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">No Projects Yet</h3>
        <p className="text-sm text-gray-600">Start by calculating your first deadline above.</p>
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {projects.map((project) => {
          const prelimDays = calculateDaysRemaining(project.prelim_deadline);
          const status = getStatusConfig(prelimDays);
          const progressPercent = getProgressPercent(prelimDays);

          return (
            <div
              key={project.id}
              onClick={() => handleCardClick(project)}
              className="bg-card rounded-xl border-2 border-border p-6 hover:shadow-lg hover:border-primary/30 transition-all cursor-pointer"
            >
              {/* Header with badges */}
              <div className="flex justify-between items-start mb-4">
                <span className={`px-3 py-1 rounded-md text-xs font-bold ${status.badgeBg} ${status.badgeText}`}>
                  {status.label}
                </span>
                <span className={`px-3 py-1 rounded-md text-sm font-bold ${status.daysBg} ${status.daysText}`}>
                  {prelimDays} days
                </span>
              </div>

              {/* Project Name */}
              <h3 className="text-lg font-bold text-foreground mb-2 line-clamp-1">
                {project.project_name || 'Unnamed Project'}
              </h3>

              {/* Client & State */}
              <div className="flex items-center gap-2 mb-3">
                <MapPin className="h-4 w-4 text-muted-foreground shrink-0" />
                <p className="text-sm text-muted-foreground truncate">
                  {project.client_name || 'Client'} • {project.state}
                </p>
              </div>

              {/* Deadline Info */}
              <div className="space-y-2 mb-4">
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground shrink-0" />
                  <p className="text-sm text-muted-foreground">
                    Prelim: {new Date(project.prelim_deadline).toLocaleDateString('en-US', { 
                      month: 'short', 
                      day: 'numeric'
                    })}
                  </p>
                </div>
                {project.amount > 0 && (
                  <div className="flex items-center gap-2">
                    <DollarSign className="h-4 w-4 text-muted-foreground shrink-0" />
                    <p className="text-sm text-muted-foreground">
                      ${project.amount.toLocaleString()}
                    </p>
                  </div>
                )}
              </div>

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

      {/* Notification Modal */}
      {selectedProject && (
        <NotificationModal
          project={selectedProject}
          isOpen={modalOpen}
          onClose={() => {
            setModalOpen(false);
            setSelectedProject(null);
          }}
          userTier={userTier}
        />
      )}
    </>
  );
};

