import { useState } from "react";
import { PhoneCall, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { campaignsAPI } from "../../lib/api";

/**
 * Places one outbound Bolna call using the currently selected campaign agent.
 * Does not dial until the user clicks the button.
 */
export default function TestCallControls({ disabled = false, compact = false }) {
  const [phone, setPhone] = useState("");
  const [calling, setCalling] = useState(false);

  const handleCall = async () => {
    const digits = String(phone || "").replace(/\D/g, "").slice(-10);
    if (digits.length !== 10) {
      toast.error("Enter a valid 10-digit mobile number");
      return;
    }
    setCalling(true);
    try {
      const res = await campaignsAPI.placeTestCall(phone);
      const executionId = res.data?.execution_id;
      toast.success(
        executionId ? `Call queued (${executionId})` : "Call queued with Bolna"
      );
    } catch (error) {
      toast.error(error.response?.data?.detail || "Could not place the call");
    } finally {
      setCalling(false);
    }
  };

  return (
    <div
      className={
        compact
          ? "flex flex-wrap items-center gap-2"
          : "flex flex-col gap-2 sm:flex-row sm:items-center"
      }
    >
      <Input
        type="tel"
        inputMode="numeric"
        autoComplete="tel"
        placeholder="10-digit mobile number"
        value={phone}
        onChange={(event) => setPhone(event.target.value)}
        disabled={disabled || calling}
        className="h-9 w-full sm:w-52 bg-[#1A1A1A] border-white/10 text-white placeholder:text-[#737373]"
        data-testid="test-call-phone"
      />
      <Button
        type="button"
        onClick={handleCall}
        disabled={disabled || calling}
        className="bg-[#C5A059] text-black hover:bg-[#E5C585]"
        data-testid="test-call-submit"
      >
        {calling ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <PhoneCall className="mr-2 h-4 w-4" />
        )}
        {calling ? "Calling…" : "Place test call"}
      </Button>
    </div>
  );
}
