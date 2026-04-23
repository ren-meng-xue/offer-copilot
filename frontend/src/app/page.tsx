
import { AuthGuard } from "@/features/auth/components/auth-guard";

export default function Home() {
  return (
    <AuthGuard>
      <div>hello,OfferCopilot</div>
    </AuthGuard>
  );
}
