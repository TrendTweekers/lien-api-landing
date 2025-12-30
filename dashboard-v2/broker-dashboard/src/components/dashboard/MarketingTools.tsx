import { Copy, Check, Mail, MessageSquare, Linkedin, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useState } from "react";
import { toast } from "sonner";

interface MarketingToolsProps {
  referralLink: string;
  brokerName: string;
}

export const MarketingTools = ({ referralLink, brokerName }: MarketingToolsProps) => {
  const [copiedLink, setCopiedLink] = useState(false);

  const copyToClipboard = (text: string, isLink = false) => {
    navigator.clipboard.writeText(text);
    if (isLink) {
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    }
    toast.success("Copied to clipboard");
  };

  const templates = {
    email: {
      subject: "Never Miss a Mechanics Lien Deadline Again",
      body: `Hi [CLIENT_NAME],

I wanted to share a tool that could save your business thousands of dollars.

LienDeadline.com calculates mechanics lien filing deadlines instantly. Building material suppliers lose $1.2 billion per year by missing these critical deadlines.

Here's what makes it valuable:
- Calculate deadlines in 0.3 seconds (vs 30-60 seconds manually)
- API integration for your ERP/accounting software
- $299/month per branch (60% cheaper than alternatives)
- First 50 calculations free - no credit card required

Try it free: ${referralLink}

If you have questions, feel free to reach out.

Best regards,
${brokerName}`
    },
    linkedin: {
      body: `🚨 Building suppliers: Missing lien deadlines costs $1.2B/year.

LienDeadline calculates deadlines in 0.3s via API. $299/mo, 60% cheaper than alternatives.

Try free: ${referralLink}

#ConstructionTech #LienManagement`
    },
    sms: {
      body: `Hi! Check out LienDeadline - calculates mechanics lien deadlines instantly. Try free: ${referralLink}`
    }
  };

  const handleEmailShare = () => {
    const mailtoLink = `mailto:?subject=${encodeURIComponent(templates.email.subject)}&body=${encodeURIComponent(templates.email.body)}`;
    window.location.href = mailtoLink;
  };

  const handleLinkedinShare = () => {
    // LinkedIn only allows sharing a URL via share-offsite, but we can try to open the feed
    // or just copy the text and open linkedin
    copyToClipboard(templates.linkedin.body);
    window.open('https://www.linkedin.com/feed/', '_blank');
    toast.info("Text copied! Paste it into your LinkedIn post.");
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Marketing Tools</CardTitle>
        <CardDescription>Share your unique link to earn commissions</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <Label>Your Referral Link</Label>
          <div className="flex gap-2">
            <Input value={referralLink} readOnly />
            <Button variant="outline" size="icon" onClick={() => copyToClipboard(referralLink, true)}>
              {copiedLink ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
        </div>

        <Tabs defaultValue="email">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="email" className="flex items-center gap-2">
              <Mail className="h-4 w-4" /> Email
            </TabsTrigger>
            <TabsTrigger value="linkedin" className="flex items-center gap-2">
              <Linkedin className="h-4 w-4" /> LinkedIn
            </TabsTrigger>
            <TabsTrigger value="sms" className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4" /> SMS
            </TabsTrigger>
          </TabsList>
          
          <TabsContent value="email" className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label>Subject Line</Label>
              <div className="flex gap-2">
                <Input value={templates.email.subject} readOnly />
                <Button variant="outline" size="icon" onClick={() => copyToClipboard(templates.email.subject)}>
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Body</Label>
              <div className="relative">
                <Textarea value={templates.email.body} readOnly rows={12} className="font-mono text-sm" />
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="absolute top-2 right-2 h-8 w-8 p-0" 
                  onClick={() => copyToClipboard(templates.email.body)}
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <Button onClick={handleEmailShare} className="w-full">
              <Mail className="mr-2 h-4 w-4" /> Open in Mail App
            </Button>
          </TabsContent>

          <TabsContent value="linkedin" className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label>Post Content (280 char optimized)</Label>
              <div className="relative">
                <Textarea value={templates.linkedin.body} readOnly rows={6} className="font-mono text-sm" />
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="absolute top-2 right-2 h-8 w-8 p-0" 
                  onClick={() => copyToClipboard(templates.linkedin.body)}
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <Button onClick={handleLinkedinShare} className="w-full bg-[#0077b5] hover:bg-[#006399]">
              <Linkedin className="mr-2 h-4 w-4" /> Copy & Open LinkedIn
            </Button>
          </TabsContent>

          <TabsContent value="sms" className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label>Message Content</Label>
              <div className="relative">
                <Textarea value={templates.sms.body} readOnly rows={3} className="font-mono text-sm" />
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="absolute top-2 right-2 h-8 w-8 p-0" 
                  onClick={() => copyToClipboard(templates.sms.body)}
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div className="text-sm text-muted-foreground">
              <p>Character count: {templates.sms.body.length} / 160</p>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
};
