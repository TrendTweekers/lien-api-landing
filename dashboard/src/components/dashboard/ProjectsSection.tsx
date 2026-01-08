import { useState } from "react";
import { LayoutGrid, LayoutList, RefreshCw, Download } from "lucide-react";
import { ProjectsCardView } from "./ProjectsCardView";
import { Button } from "@/components/ui/button";

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

interface ProjectsSectionProps {
  projects: Project[];
  userTier: 'free' | 'basic' | 'automated' | 'enterprise';
  onRefresh: () => void;
  ProjectsTableComponent: React.ComponentType<any>; // Your existing ProjectsTable component
}

export const ProjectsSection = ({ 
  projects, 
  userTier, 
  onRefresh,
  ProjectsTableComponent
}: ProjectsSectionProps) => {
  const [view, setView] = useState<'table' | 'card'>('table');
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    await onRefresh();
    setTimeout(() => setRefreshing(false), 500);
  };

  const handleExportCSV = () => {
    // Create CSV content
    const headers = ['Project', 'Client', 'Invoice Date', 'Amount', 'State', 'Prelim Deadline', 'Lien Deadline'];
    const rows = projects.map(p => [
      p.project_name || 'Unnamed',
      p.client_name || 'Client',
      p.invoice_date,
      p.amount,
      p.state,
      p.prelim_deadline,
      p.lien_deadline
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    // Download
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `liendeadline-projects-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  return (
    <div data-projects-section className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h2 className="text-2xl font-bold text-foreground">Your Projects</h2>
        
        {/* Controls */}
        <div className="flex items-center gap-2">
          {/* Refresh */}
          <Button
            onClick={handleRefresh}
            variant="outline"
            size="sm"
            disabled={refreshing}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>

          {/* View Toggle */}
          <div className="flex border border-gray-300 rounded-lg overflow-hidden">
            <button
              onClick={() => setView('table')}
              className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2 ${
                view === 'table'
                  ? 'bg-orange-500 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              <LayoutList className="h-4 w-4" />
              <span className="hidden sm:inline">Table View</span>
            </button>
            <button
              onClick={() => setView('card')}
              className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2 border-l border-gray-300 ${
                view === 'card'
                  ? 'bg-orange-500 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              <LayoutGrid className="h-4 w-4" />
              <span className="hidden sm:inline">Card View</span>
            </button>
          </div>

          {/* Export CSV */}
          <Button
            onClick={handleExportCSV}
            className="bg-green-600 hover:bg-green-700 text-white gap-2"
            size="sm"
          >
            <Download className="h-4 w-4" />
            <span className="hidden sm:inline">Export to CSV</span>
          </Button>
        </div>
      </div>

      {/* View Content */}
      <div>
        {view === 'card' ? (
          <ProjectsCardView projects={projects} userTier={userTier} />
        ) : (
          <ProjectsTableComponent />
        )}
      </div>
    </div>
  );
};

