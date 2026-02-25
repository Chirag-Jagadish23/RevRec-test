import "./globals.css";
import { Toaster } from "sonner";
import { WorkspaceProvider } from "@/src/components/providers/WorkspaceProvider";
import AppShell from "@/src/components/AppShell";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <WorkspaceProvider>
          <AppShell>{children}</AppShell>
          <Toaster richColors />
        </WorkspaceProvider>
      </body>
    </html>
  );
}
