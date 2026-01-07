import { useState, useEffect } from "react";
import { Calendar, MapPin, Calculator, Save, AlertCircle, Building2, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { differenceInCalendarDays } from "date-fns";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { usePlan } from "@/hooks/usePlan";
import { UpgradeModal } from "@/components/UpgradeModal";

const US_STATES = [
  { name: "Alabama", code: "AL" },
  { name: "Alaska", code: "AK" },
  { name: "Arizona", code: "AZ" },
  { name: "Arkansas", code: "AR" },
  { name: "California", code: "CA" },
  { name: "Colorado", code: "CO" },
  { name: "Connecticut", code: "CT" },
  { name: "Delaware", code: "DE" },
  { name: "Florida", code: "FL" },
  { name: "Georgia", code: "GA" },
  { name: "Hawaii", code: "HI" },
  { name: "Idaho", code: "ID" },
  { name: "Illinois", code: "IL" },
  { name: "Indiana", code: "IN" },
  { name: "Iowa", code: "IA" },
  { name: "Kansas", code: "KS" },
  { name: "Kentucky", code: "KY" },
  { name: "Louisiana", code: "LA" },
  { name: "Maine", code: "ME" },
  { name: "Maryland", code: "MD" },
  { name: "Massachusetts", code: "MA" },
  { name: "Michigan", code: "MI" },
  { name: "Minnesota", code: "MN" },
  { name: "Mississippi", code: "MS" },
  { name: "Missouri", code: "MO" },
  { name: "Montana", code: "MT" },
  { name: "Nebraska", code: "NE" },
  { name: "Nevada", code: "NV" },
  { name: "New Hampshire", code: "NH" },
  { name: "New Jersey", code: "NJ" },
  { name: "New Mexico", code: "NM" },
  { name: "New York", code: "NY" },
  { name: "North Carolina", code: "NC" },
  { name: "North Dakota", code: "ND" },
  { name: "Ohio", code: "OH" },
  { name: "Oklahoma", code: "OK" },
  { name: "Oregon", code: "OR" },
  { name: "Pennsylvania", code: "PA" },
  { name: "Rhode Island", code: "RI" },
  { name: "South Carolina", code: "SC" },
  { name: "South Dakota", code: "SD" },
  { name: "Tennessee", code: "TN" },
  { name: "Texas", code: "TX" },
  { name: "Utah", code: "UT" },
  { name: "Vermont", code: "VT" },
  { name: "Virginia", code: "VA" },
  { name: "Washington", code: "WA" },
  { name: "West Virginia", code: "WV" },
  { name: "Wisconsin", code: "WI" },
  { name: "Wyoming", code: "WY" }
];

const STATE_TO_ABBR: Record<string, string> = {
  "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
  "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
  "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
  "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
  "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO",
  "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
  "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
  "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
  "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
  "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY"
};

export const DeadlineCalculator = () => {
  const { toast } = useToast();
  const { planInfo } = usePlan();
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedState, setSelectedState] = useState("");
  const [projectType, setProjectType] = useState("commercial");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [projectName, setProjectName] = useState("");
  const [clientName, setClientName] = useState("");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [reminder1Day, setReminder1Day] = useState(false);
  const [reminder7Days, setReminder7Days] = useState(false);
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);
  // Track supported states from backend (same source as ImportedInvoicesTable)
  const [supportedStates, setSupportedStates] = useState<Set<string>>(new Set());
  
  // Check if calculations are locked (free plan limit reached)
  const isCalculationsLocked = planInfo.plan === "free" && (planInfo.remainingCalculations ?? Infinity) <= 0;

  // Fetch supported states from backend (same endpoint as ImportedInvoicesTable)
  useEffect(() => {
    const fetchSupportedStates = async () => {
      try {
        const res = await fetch("/api/v1/supported-states");
        if (res.ok) {
          const data = await res.json();
          const states = data.states || [];
          setSupportedStates(new Set(states.map((s: string) => s.toUpperCase())));
        }
      } catch (e) {
        console.error("Failed to fetch supported states:", e);
        // Fallback: assume all states are supported
        setSupportedStates(new Set(US_STATES.map(s => s.code)));
      }
    };
    fetchSupportedStates();
  }, []);

  // States that require project type (Commercial/Residential)
  const STATES_WITH_PROJECT_TYPE = ['TX', 'CA', 'FL', 'AZ', 'NV', 'MD', 'GA', 'MN', 'OR', 'WA'];
  
  // Resolve state abbreviation for API payload
  const stateAbbr = STATE_TO_ABBR[selectedState] || selectedState;
  
  // Check if project type dropdown should be shown
  const showDropdown = STATES_WITH_PROJECT_TYPE.includes(selectedState);
  
  // Filter US_STATES to only show supported states
  const availableStates = supportedStates.size > 0
    ? US_STATES.filter(state => supportedStates.has(state.code))
    : US_STATES; // Fallback to all states if not loaded yet

  const handleCalculate = async () => {
    // Check if calculations are locked
    if (isCalculationsLocked) {
      setUpgradeModalOpen(true);
      return;
    }
    
    if (!selectedState || !date) {
      toast({
        title: "Missing Information",
        description: "Please select a state and date.",
        variant: "destructive",
      });
      return;
    }
    
    // Debug logging
    console.log("🚀 Sending Calculation Payload:", { 
      invoice_date: date, 
      state: selectedState, 
      project_type: projectType 
    });
    
    setLoading(true);
    try {
      // Switched to /api/calculate to match homepage logic and avoid 502 errors
      const response = await fetch("/api/calculate", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          state: stateAbbr, // Use the abbreviation for API safety
          invoice_date: date,
          project_type: projectType
        })
      });
      
      if (!response.ok) throw new Error("Calculation failed");
      
      const data = await response.json();
      console.log("🔍 API Calculation Response:", data);
      
      setResult({
        prelimDeadline: data.preliminary_notice.deadline,
        prelimDays: data.preliminary_notice.days_from_now,
        lienDeadline: data.lien_filing.deadline,
        lienDays: data.lien_filing.days_from_now
      });
      
      toast({
        title: "Calculation Complete",
        description: "Deadlines have been updated.",
      });
    } catch (error) {
      console.error(error);
      toast({
        title: "Error",
        description: "Failed to calculate deadlines.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!result) return;
    
    try {
      const token = localStorage.getItem('session_token');
      const headers: HeadersInit = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const response = await fetch("/api/calculations/save", {
        method: "POST",
        headers,
        body: JSON.stringify({
          state: stateAbbr, // Use abbreviation
          invoice_date: date,
          project_name: projectName || "Unnamed Project",
          client_name: clientName || "Client",
          invoiceAmount: parseFloat(amount) || 0,
          description: notes,
          prelim_deadline: result.prelimDeadline,
          lien_deadline: result.lienDeadline,
          reminder_1day: reminder1Day ? 1 : 0,
          reminder_7days: reminder7Days ? 1 : 0
        })
      });

      if (!response.ok) {
        // Check for 402 Payment Required with billing error codes
        if (response.status === 402) {
          try {
            const errorData = await response.json();
            const errorCode = errorData.code || errorData.detail?.code;
            
            if (errorCode === "LIMIT_REACHED" || errorCode === "UPGRADE_REQUIRED") {
              // Open upgrade modal instead of showing error
              setUpgradeModalOpen(true);
              return;
            }
          } catch (e) {
            // If JSON parsing fails, still open upgrade modal for 402
            setUpgradeModalOpen(true);
            return;
          }
        }
        throw new Error("Save failed");
      }

      toast({
        title: "Saved",
        description: "Project saved to dashboard.",
      });
      
      // Dispatch custom event to notify ProjectsTable
      window.dispatchEvent(new Event('project-saved'));

      // Clear form
      setResult(null);
      setProjectName("");
      setClientName("");
      setAmount("");
      setNotes("");
      setReminder1Day(false);
      setReminder7Days(false);
    } catch (error) {
       toast({
        title: "Error",
        description: "Failed to save project.",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="space-y-6">
      {isCalculationsLocked && (
        <div className="flex items-center gap-3 p-4 bg-orange-50 border border-orange-200 rounded-lg">
          <Lock className="h-5 w-5 text-orange-600" />
          <div className="flex-1">
            <p className="text-sm font-medium text-orange-900">
              Free Plan Limit Reached
            </p>
            <p className="text-xs text-orange-700 mt-1">
              You've used all 3 free calculations this month. Upgrade for unlimited calculations and automation.
            </p>
          </div>
          <Button
            size="sm"
            onClick={() => setUpgradeModalOpen(true)}
            className="bg-orange-600 hover:bg-orange-700 text-white"
          >
            Upgrade Now
          </Button>
        </div>
      )}
      
      <div className="bg-card rounded-xl p-6 border border-border card-shadow">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center">
            <Calculator className="h-5 w-5 text-primary-foreground" />
          </div>
          <h2 className="text-lg font-semibold text-foreground">Calculate New Deadline</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label className="text-sm text-foreground flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              Invoice/Delivery Date
            </Label>
            <Input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="bg-background border-border focus:border-primary focus:ring-primary/20"
            />
          </div>

          <div className="space-y-2">
            <Label className="text-sm text-foreground flex items-center gap-2">
              <MapPin className="h-4 w-4 text-muted-foreground" />
              State
            </Label>
            <Select value={selectedState} onValueChange={setSelectedState}>
              <SelectTrigger className="bg-background border-border focus:border-primary focus:ring-primary/20">
                <SelectValue placeholder="Select a state..." />
              </SelectTrigger>
              <SelectContent className="bg-card border-border">
                {availableStates.map((state) => (
                  <SelectItem key={state.code} value={state.code}>
                    {state.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {showDropdown && (
            <div className="space-y-2">
              <Label className="text-sm text-foreground flex items-center gap-2">
                <Building2 className="h-4 w-4 text-muted-foreground" />
                Project Type
              </Label>
              <Select value={projectType} onValueChange={setProjectType}>
                <SelectTrigger className="bg-background border-border focus:border-primary focus:ring-primary/20">
                  <SelectValue placeholder="Select project type" />
                </SelectTrigger>
                <SelectContent className="bg-card border-border">
                  <SelectItem value="commercial">Commercial</SelectItem>
                  <SelectItem value="residential">Residential</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
        </div>

        <Button 
          onClick={handleCalculate}
          disabled={loading}
          className="w-full mt-6 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold h-12 text-base"
        >
          {loading ? "Calculating..." : (
            <>
              <Calculator className="h-5 w-5 mr-2" />
              Calculate Deadlines
            </>
          )}
        </Button>
      </div>

      {result && (
        <Card className="animate-fade-in border-border">
          <CardHeader>
            <CardTitle>Calculation Results</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-lg" style={{ backgroundColor: '#d1fae5', border: '1px solid #86efac' }}>
                <h3 className="font-semibold mb-1 text-green-700">PRELIMINARY NOTICE</h3>
                <p className="text-2xl font-bold text-foreground">{result.prelimDeadline || "Not Required"}</p>
                <p className="text-sm text-muted-foreground">
                  {result.prelimDays !== null && result.prelimDays !== undefined 
                    ? `${result.prelimDays} days remaining` 
                    : <span className="text-gray-400">Not Required</span>}
                </p>
              </div>
              <div className="p-4 rounded-lg" style={{ backgroundColor: '#fed7aa', border: '1px solid #fdba74' }}>
                <h3 className="font-semibold mb-1 text-orange-700">LIEN FILING DEADLINE</h3>
                <p className="text-2xl font-bold text-foreground">{result.lienDeadline || "Not Required"}</p>
                <p className="text-sm text-muted-foreground">
                  {result.lienDays !== null && result.lienDays !== undefined 
                    ? `${result.lienDays} days remaining` 
                    : <span className="text-gray-400">Not Required</span>}
                </p>
              </div>
            </div>

            <div className="pt-4 border-t border-border space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Project Name</Label>
                  <Input 
                    placeholder="Enter project name" 
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Client Name</Label>
                  <Input 
                    placeholder="Enter client name" 
                    value={clientName}
                    onChange={(e) => setClientName(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Amount ($)</Label>
                  <Input 
                    type="number" 
                    placeholder="0.00"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Notes</Label>
                  <Input 
                    placeholder="Optional notes" 
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label>Reminders</Label>
                <div className="flex gap-4">
                  <div className="flex items-center space-x-2">
                    <input 
                      type="checkbox" 
                      id="reminder1Day"
                      checked={reminder1Day}
                      onChange={(e) => setReminder1Day(e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    <label htmlFor="reminder1Day" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                      1 Day Before
                    </label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input 
                      type="checkbox" 
                      id="reminder7Days"
                      checked={reminder7Days}
                      onChange={(e) => setReminder7Days(e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    <label htmlFor="reminder7Days" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                      7 Days Before
                    </label>
                  </div>
                </div>
              </div>

              <Button onClick={handleSave} className="w-full" variant="secondary">
                <Save className="h-4 w-4 mr-2" />
                Save to Dashboard
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
      
      <UpgradeModal open={upgradeModalOpen} onOpenChange={setUpgradeModalOpen} />
    </div>
  );
};
