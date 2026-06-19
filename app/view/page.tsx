import type { Metadata } from "next";
import { Suspense } from "react";
import { DashboardViewer } from "@/components/dashboard-viewer";

export const metadata: Metadata = {
  title: "Dashboard viewer",
  description: "Open a published QGIS Dashboard, fully interactive in your browser.",
};

export default function ViewPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto h-[calc(100vh-4rem)] max-w-7xl px-5 py-5">
          <div className="tile h-full animate-pulse opacity-60" />
        </div>
      }
    >
      <DashboardViewer />
    </Suspense>
  );
}
