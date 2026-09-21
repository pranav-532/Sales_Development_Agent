import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { useControl } from "@/context/ControlContext";

export default function Boot({ children }: { children: ReactNode }) {
  const { ready, loadError, reload } = useControl();

  if (ready) return <>{children}</>;

  return (
    <div className="flex h-screen items-center justify-center bg-background p-6">
      <div className="max-w-md space-y-3 text-center">
        {loadError ? (
          <>
            <h1 className="text-xl font-semibold">Cannot load the workspace</h1>
            <p className="text-sm text-muted-foreground">{loadError}</p>
            <Button onClick={() => void reload()}>Try again</Button>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Loading workspace...</p>
        )}
      </div>
    </div>
  );
}