import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { format } from "date-fns";

interface Referral {
  customer_email: string;
  amount: number;
  payout: number;
  payout_type: string;
  status: string;
  created_at: string;
}

interface ReferralsTableProps {
  referrals: Referral[];
}

export const ReferralsTable = ({ referrals }: ReferralsTableProps) => {
  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "paid":
        return "default"; // black/primary
      case "pending":
        return "secondary"; // gray
      case "on_hold":
        return "destructive"; // red
      default:
        return "outline";
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Referrals</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Sale Amount</TableHead>
              <TableHead>Commission</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {referrals.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  No referrals yet. Share your link to get started!
                </TableCell>
              </TableRow>
            ) : (
              referrals.map((referral, index) => (
                <TableRow key={index}>
                  <TableCell>
                    {referral.created_at ? format(new Date(referral.created_at), "MMM d, yyyy") : "-"}
                  </TableCell>
                  <TableCell>{referral.customer_email}</TableCell>
                  <TableCell>${referral.amount.toFixed(2)}</TableCell>
                  <TableCell className="font-medium text-green-600">
                    ${referral.payout.toFixed(2)}
                  </TableCell>
                  <TableCell className="capitalize">{referral.payout_type}</TableCell>
                  <TableCell>
                    <Badge variant={getStatusColor(referral.status)}>
                      {referral.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
};
