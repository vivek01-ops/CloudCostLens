import { FlaskConical } from "lucide-react";

/**
 * Unmissable banner shown wherever demonstration fixtures are rendered. This guarantees
 * sample data is never misrepresented as live AWS data.
 */
export function DemoBanner({ note }: { note?: string }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
      <FlaskConical className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>
        <strong className="font-semibold">Sample data.</strong>{" "}
        {note ?? "This view is running on clearly labeled demonstration fixtures, not live AWS data."}
      </span>
    </div>
  );
}