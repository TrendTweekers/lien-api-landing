import { useState } from "react";
import { Calendar, MapPin, Calculator, Save, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";

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

export const DeadlineCalculator = () => {
  const { toast } = useToast();
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedState, setSelectedState] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [projectName, setProjectName] = useState("");
  const [clientName, setClientName] = useState("");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [reminder1Day, setReminder1Day] = useState(false);
  const [reminder7Days, setReminder7Days] = useState(false);

  const handleCalculate = async () => {
    if (!selectedState || !date) {
      toast({
        title: "Missing Information",
        description: "Please select a state and date.",
        variant: "destructive",
      });
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch("/api/v1/calculate-deadline", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          state: selectedState,
          invoice_date: date,
          project_type: "commercial"
        })
      });
      
      if (!response.ok) throw new Error("Calculation failed");
      
      const data = await response.json();
      setResult(data);
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
          state: selectedState,
          invoice_date: date,
          project_name: projectName || "Unnamed Project",
          client_name: clientName || "Client",
          amount: parseFloat(amount) || 0,
          description: notes,
          prelim_deadline: result.preliminary_notice.deadline,
          lien_deadline: result.lien_filing.deadline,
          reminder_1day: reminder1Day ? 1 : 0,
          reminder_7days: reminder7Days ? 1 : 0
        })
      });

      if (!response.ok) throw new Error("Save failed");

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
                {US_STATES.map((state) => (
                  <SelectItem key={state.code} value={state.code}>
                    {state.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
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
              <div className="p-4 rounded-lg bg-accent/10 border border-accent/20">
                <h3 className="font-semibold mb-1 text-accent-foreground">Preliminary Notice</h3>
                <p className="text-2xl font-bold">{result.preliminary_notice.deadline}</p>
                <p className="text-sm text-muted-foreground">{result.preliminary_notice.days_from_now} days remaining</p>
              </div>
              <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20">
                <h3 className="font-semibold mb-1 text-destructive">Lien Filing</h3>
                <p className="text-2xl font-bold">{result.lien_filing.deadline}</p>
                <p className="text-sm text-muted-foreground">{result.lien_filing.days_from_now} days remaining</p>
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
    </div>
  );
};
