import { initSentry } from "@/lib/sentry";

initSentry({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT,
  tracesSampleRateStr: process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE,
});
