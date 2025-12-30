import { Copy, Check, Mail, MessageSquare, Linkedin } from "lucide-react";
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
}

export const MarketingTools = ({ referralLink }: MarketingToolsProps) => {
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
      subject: "Save on your lien deadlines",
      body: `Hi,\n\nI found a great tool for calculating lien deadlines and ensuring you never miss a filing date. It's called LienDeadline.\n\nCheck it out here: ${referralLink}\n\nBest,`
    },
    linkedin: {
      body: `Contractors and suppliers: stop worrying about missed lien deadlines. I'm using LienDeadline to track everything automatically.\n\nTry it out: ${referralLink} #construction #liens`
    },
    sms: {
      body: `Hey, check out this lien deadline calculator: ${referralLink}. It saves a ton of time.`
    }
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
                <Textarea value={templates.email.body} readOnly rows={6} />
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
          </TabsContent>

          <TabsContent value="linkedin" className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label>Post Content</Label>
              <div className="relative">
                <Textarea value={templates.linkedin.body} readOnly rows={4} />
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
          </TabsContent>

          <TabsContent value="sms" className="space-y-4 mt-4">
            <div className="space-y-2">
              <Label>Message</Label>
              <div className="relative">
                <Textarea value={templates.sms.body} readOnly rows={3} />
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
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
};
