import { useState } from "react";
import { 
  CheckCircle2, 
  DollarSign, 
  TrendingUp, 
  Users, 
  ShieldCheck, 
  ArrowRight, 
  Calculator,
  BarChart3,
  PieChart,
  LayoutDashboard
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { useToast } from "@/hooks/use-toast";

export default function PartnerProgramPage() {
  const { toast } = useToast();
  
  // Calculator State
  const [clientCount, setClientCount] = useState([10]);
  const [model, setModel] = useState<"bounty" | "recurring">("recurring");
  
  // Form State
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    fullName: "",
    email: "",
    companyName: "",
    website: "",
    role: ""
  });

  const clients = clientCount[0];
  const bountyEarnings = clients * 500;
  const recurringEarnings = clients * 50; // Monthly
  const recurringAnnual = recurringEarnings * 12;

  const handleSliderChange = (value: number[]) => {
    setClientCount(value);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await fetch("/api/v1/apply-partner", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) throw new Error("Submission failed");

      toast({
        title: "Application Received!",
        description: "We'll be in touch shortly. Welcome to the program!",
        className: "bg-green-50 border-green-200 text-green-800",
      });
      
      setFormData({
        fullName: "",
        email: "",
        companyName: "",
        website: "",
        role: ""
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Something went wrong. Please try again later.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      {/* Public Header */}
      <header className="sticky top-0 z-50 w-full border-b border-white/10 bg-white/95 backdrop-blur-sm shadow-sm">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-orange-600 flex items-center justify-center">
              <span className="text-white font-bold text-sm">L</span>
            </div>
            <span className="text-xl font-bold text-gray-900">LienDeadline</span>
          </div>
          <Button variant="ghost" className="text-gray-600 hover:text-orange-600 font-medium" onClick={() => window.location.href = '/'}>
            Back to Dashboard
          </Button>
        </div>
      </header>
      
      {/* 1. Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-orange-500 to-orange-400 text-white pt-24 pb-32">
        <div className="container mx-auto px-4 relative z-10">
          <div className="max-w-3xl mx-auto text-center">
            <h1 className="text-4xl md:text-5xl font-bold mb-6 tracking-tight">
              Partner With LienDeadline
            </h1>
            <p className="text-xl md:text-2xl opacity-90 mb-8 font-light">
              Help construction professionals protect their payment rights while earning recurring revenue.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Button 
                size="lg" 
                className="bg-white text-orange-600 hover:bg-gray-100 font-semibold text-lg px-8 h-14 w-full sm:w-auto shadow-lg"
                onClick={() => document.getElementById('apply-form')?.scrollIntoView({ behavior: 'smooth' })}
              >
                Become a Partner
              </Button>
              <Button 
                variant="outline" 
                size="lg" 
                className="bg-transparent border-white text-white hover:bg-white/10 font-semibold text-lg px-8 h-14 w-full sm:w-auto"
                onClick={() => document.getElementById('calculator')?.scrollIntoView({ behavior: 'smooth' })}
              >
                Calculate Earnings
              </Button>
            </div>
          </div>
        </div>
        {/* Abstract shapes background */}
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none opacity-10">
          <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-white blur-3xl"></div>
          <div className="absolute bottom-0 right-0 w-[500px] h-[500px] rounded-full bg-white blur-3xl"></div>
        </div>
      </section>

      {/* 2. Benefits Section */}
      <section className="py-20 -mt-16 relative z-20">
        <div className="container mx-auto px-4">
          <div className="grid md:grid-cols-3 gap-8">
            <Card className="border-none shadow-xl bg-white/95 backdrop-blur">
              <CardHeader>
                <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center mb-4">
                  <ShieldCheck className="h-6 w-6 text-orange-600" />
                </div>
                <CardTitle className="text-xl">Add Value to Your Clients</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-600">
                  Help them avoid costly missed deadlines. Protect their lien rights automatically without adding to your workload.
                </p>
              </CardContent>
            </Card>

            <Card className="border-none shadow-xl bg-white/95 backdrop-blur">
              <CardHeader>
                <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4">
                  <DollarSign className="h-6 w-6 text-green-600" />
                </div>
                <CardTitle className="text-xl">Recurring Revenue</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-600">
                  Build a passive income stream. Earn up to 20% recurring commission on every subscription for the life of the customer.
                </p>
              </CardContent>
            </Card>

            <Card className="border-none shadow-xl bg-white/95 backdrop-blur">
              <CardHeader>
                <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
                  <Users className="h-6 w-6 text-blue-600" />
                </div>
                <CardTitle className="text-xl">Trusted Partnership</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-600">
                  We handle everything: onboarding, support, billing, and product updates. You just make the introduction.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* 3. Commission Calculator */}
      <section id="calculator" className="py-20 bg-white">
        <div className="container mx-auto px-4">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold text-gray-900 mb-4">Estimate Your Earnings</h2>
              <p className="text-lg text-gray-600">See how much you can earn by partnering with us</p>
            </div>

            <div className="grid lg:grid-cols-2 gap-12 items-center">
              {/* Controls */}
              <div className="space-y-8">
                <div className="bg-gray-50 p-8 rounded-2xl border border-gray-100">
                  <div className="mb-8">
                    <Label className="text-lg font-semibold mb-4 block">
                      Number of Clients: <span className="text-orange-600 text-2xl ml-2">{clients}</span>
                    </Label>
                    <Slider 
                      value={clientCount} 
                      onValueChange={handleSliderChange} 
                      max={100} 
                      min={1} 
                      step={1}
                      className="py-4"
                    />
                    <div className="flex justify-between text-sm text-gray-500 mt-2">
                      <span>1 Client</span>
                      <span>50 Clients</span>
                      <span>100+ Clients</span>
                    </div>
                  </div>

                  <div>
                    <Label className="text-lg font-semibold mb-4 block">Commission Model</Label>
                    <div className="grid grid-cols-2 gap-4">
                      <button
                        onClick={() => setModel("recurring")}
                        className={`p-4 rounded-xl border-2 transition-all ${
                          model === "recurring" 
                            ? "border-orange-500 bg-orange-50 text-orange-700" 
                            : "border-gray-200 hover:border-orange-200 text-gray-600"
                        }`}
                      >
                        <div className="font-bold mb-1">Recurring</div>
                        <div className="text-sm opacity-80">15% Monthly</div>
                      </button>
                      <button
                        onClick={() => setModel("bounty")}
                        className={`p-4 rounded-xl border-2 transition-all ${
                          model === "bounty" 
                            ? "border-orange-500 bg-orange-50 text-orange-700" 
                            : "border-gray-200 hover:border-orange-200 text-gray-600"
                        }`}
                      >
                        <div className="font-bold mb-1">Bounty</div>
                        <div className="text-sm opacity-80">$500 One-time</div>
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Results */}
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-br from-orange-100 to-orange-50 rounded-3xl transform rotate-3 scale-105 opacity-50"></div>
                <div className="relative bg-white p-10 rounded-3xl shadow-xl border border-gray-100 text-center">
                  <h3 className="text-xl font-medium text-gray-500 mb-6 uppercase tracking-wide">
                    {model === "recurring" ? "Projected Annual Revenue" : "Total One-Time Payout"}
                  </h3>
                  <div className="text-6xl font-bold text-gray-900 mb-4 tracking-tight">
                    ${model === "recurring" 
                        ? recurringAnnual.toLocaleString() 
                        : bountyEarnings.toLocaleString()
                    }
                  </div>
                  <div className="inline-block bg-green-100 text-green-700 px-4 py-2 rounded-full font-medium text-sm mb-8">
                    {model === "recurring" 
                      ? `$${recurringEarnings.toLocaleString()}/month recurring`
                      : "Paid upon client activation"
                    }
                  </div>
                  
                  <div className="pt-8 border-t border-gray-100">
                    <p className="text-gray-600">
                      {model === "recurring" 
                        ? "Build a sustainable revenue stream that grows with your client base."
                        : "Get immediate cash flow for every successful referral."
                      }
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Partner Dashboard Preview */}
      <section className="py-20 bg-gray-50">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">What You'll Get as a Partner</h2>
            <p className="text-lg text-gray-600">Powerful tools to track your success</p>
          </div>

          <div className="max-w-6xl mx-auto">
            <div className="bg-white rounded-2xl shadow-2xl overflow-hidden border border-gray-200">
              <div className="bg-gray-900 p-4 flex items-center gap-2 border-b border-gray-800">
                <div className="flex gap-2 mr-4">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                </div>
                <div className="bg-gray-800 text-gray-400 px-4 py-1 rounded-md text-xs font-mono flex-1 text-center">
                  partners.liendeadline.com/dashboard
                </div>
              </div>
              
              {/* Dashboard Mockup Grid */}
              <div className="p-8 grid md:grid-cols-3 gap-6 bg-gray-50/50">
                {/* Mock Card 1 */}
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="font-semibold text-gray-700">Total Earnings</h4>
                    <DollarSign className="h-5 w-5 text-green-500" />
                  </div>
                  <div className="text-3xl font-bold text-gray-900">$12,450.00</div>
                  <div className="text-sm text-green-600 mt-2 flex items-center">
                    <TrendingUp className="h-4 w-4 mr-1" /> +15% this month
                  </div>
                </div>

                {/* Mock Card 2 */}
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="font-semibold text-gray-700">Active Referrals</h4>
                    <Users className="h-5 w-5 text-blue-500" />
                  </div>
                  <div className="text-3xl font-bold text-gray-900">24</div>
                  <div className="text-sm text-gray-500 mt-2">
                    4 pending activation
                  </div>
                </div>

                {/* Mock Card 3 */}
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="font-semibold text-gray-700">Clicks</h4>
                    <BarChart3 className="h-5 w-5 text-orange-500" />
                  </div>
                  <div className="text-3xl font-bold text-gray-900">1,205</div>
                  <div className="text-sm text-gray-500 mt-2">
                    3.5% conversion rate
                  </div>
                </div>

                {/* Mock Chart Area */}
                <div className="md:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-gray-100 h-64 flex flex-col justify-center items-center text-gray-400">
                  <BarChart3 className="h-16 w-16 mb-4 opacity-20" />
                  <p>Real-time Referral Analytics</p>
                </div>

                {/* Mock Recent Activity */}
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                  <h4 className="font-semibold text-gray-700 mb-4">Recent Payouts</h4>
                  <div className="space-y-4">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="flex justify-between items-center text-sm">
                        <span className="text-gray-600">Payout #{1020 + i}</span>
                        <span className="font-medium text-green-600">+$500.00</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 6. Social Proof */}
      <section className="py-20 bg-white border-y border-gray-100">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-12">Trusted by Construction Professionals</h2>
          
          <div className="grid md:grid-cols-3 gap-8 text-center">
            <div>
              <div className="text-4xl font-bold text-orange-600 mb-2">50+</div>
              <div className="text-gray-600 font-medium">Active Partners</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-orange-600 mb-2">$150k+</div>
              <div className="text-gray-600 font-medium">Paid to Partners</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-orange-600 mb-2">100%</div>
              <div className="text-gray-600 font-medium">On-Time Payouts</div>
            </div>
          </div>
        </div>
      </section>

      {/* 5. Application Form */}
      <section id="apply-form" className="py-24 bg-gray-50">
        <div className="container mx-auto px-4">
          <div className="max-w-2xl mx-auto">
            <div className="text-center mb-10">
              <h2 className="text-3xl font-bold text-gray-900 mb-4">Join the Partner Program</h2>
              <p className="text-gray-600">
                Apply today and start earning. Construction industry professionals are auto-approved.
              </p>
            </div>

            <Card className="shadow-lg border-gray-100">
              <CardContent className="p-8">
                <form onSubmit={handleSubmit} className="space-y-6">
                  <div className="grid md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label htmlFor="fullName">Full Name</Label>
                      <Input 
                        id="fullName" 
                        name="fullName"
                        required 
                        placeholder="John Doe"
                        value={formData.fullName}
                        onChange={handleInputChange}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">Email Address</Label>
                      <Input 
                        id="email" 
                        name="email"
                        type="email" 
                        required 
                        placeholder="john@company.com"
                        value={formData.email}
                        onChange={handleInputChange}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="companyName">Company Name</Label>
                    <Input 
                      id="companyName" 
                      name="companyName"
                      required 
                      placeholder="Construction Services LLC"
                      value={formData.companyName}
                      onChange={handleInputChange}
                    />
                  </div>

                  <div className="grid md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label htmlFor="website">Website (Optional)</Label>
                      <Input 
                        id="website" 
                        name="website"
                        placeholder="www.company.com"
                        value={formData.website}
                        onChange={handleInputChange}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="role">Job Title / Role</Label>
                      <Input 
                        id="role" 
                        name="role"
                        required 
                        placeholder="e.g. Insurance Broker"
                        value={formData.role}
                        onChange={handleInputChange}
                      />
                    </div>
                  </div>

                  <div className="bg-blue-50 p-4 rounded-lg flex items-start gap-3 text-sm text-blue-700">
                    <CheckCircle2 className="h-5 w-5 shrink-0 mt-0.5" />
                    <p>
                      By applying, you agree to our Partner Terms. Auto-approval applies to verified emails from construction-related domains.
                    </p>
                  </div>

                  <Button 
                    type="submit" 
                    className="w-full h-12 text-lg font-semibold bg-orange-600 hover:bg-orange-700"
                    disabled={loading}
                  >
                    {loading ? "Submitting Application..." : "Submit Application"}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* 7. FAQ Section */}
      <section className="py-20 bg-white">
        <div className="container mx-auto px-4 max-w-3xl">
          <h2 className="text-3xl font-bold text-gray-900 mb-10 text-center">Frequently Asked Questions</h2>
          
          <Accordion type="single" collapsible className="w-full">
            <AccordionItem value="item-1">
              <AccordionTrigger className="text-lg">Who is this program for?</AccordionTrigger>
              <AccordionContent className="text-gray-600">
                This program is designed for insurance brokers, construction attorneys, accountants, and consultants who work with construction companies. If your clients deal with mechanics liens or notices, this is for you.
              </AccordionContent>
            </AccordionItem>
            
            <AccordionItem value="item-2">
              <AccordionTrigger className="text-lg">Do I need to be a business to join?</AccordionTrigger>
              <AccordionContent className="text-gray-600">
                While most of our partners are businesses, individual consultants can also join. You will need to provide tax information (W-9) to receive payouts.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="item-3">
              <AccordionTrigger className="text-lg">Can I refer international clients?</AccordionTrigger>
              <AccordionContent className="text-gray-600">
                Currently, LienDeadline is optimized for United States construction laws. We recommend referring clients who have projects within the US.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="item-4">
              <AccordionTrigger className="text-lg">What marketing materials do you provide?</AccordionTrigger>
              <AccordionContent className="text-gray-600">
                Partners get access to a dedicated dashboard with banners, email templates, one-pagers, and social media assets to help you share LienDeadline effectively.
              </AccordionContent>
            </AccordionItem>
            
            <AccordionItem value="item-5">
              <AccordionTrigger className="text-lg">How often are payouts made?</AccordionTrigger>
              <AccordionContent className="text-gray-600">
                Payouts are processed monthly via direct deposit or PayPal. There is a net-30 hold on commissions to account for any potential refunds.
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-12">
        <div className="container mx-auto px-4 text-center">
          <p className="opacity-50">© 2025 LienDeadline. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
