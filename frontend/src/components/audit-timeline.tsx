import Link from "next/link";
import { History } from "lucide-react";
import { Event } from "@/lib/api";
import { label } from "./ui";
export default function AuditTimeline({ events: list }: { events: Event[] }) {
  return (
    <div className="timeline">
      {list.slice(0, 100).map((e) => (
        <div className="event" key={e.id}>
          <span className="event-icon">
            <History size={14} />
          </span>
          <div>
            <strong>{label(e.event)}</strong>
            <p>
              {e.actor} <span>·</span>{" "}
              <Link href={"/claims/" + e.claim_id}>{e.claim_id}</Link>
              {e.data.previous_readiness !== undefined && (
                <b className="transition">
                  {" "}
                  {e.data.previous_readiness}% → {e.data.new_readiness}%
                </b>
              )}
            </p>
            {e.data.new && (
              <small>
                {e.data.previous.readiness}% → {e.data.new.readiness}% ·{" "}
                {label(e.data.new.status)}
              </small>
            )}
          </div>
          <time>
            {new Date(e.timestamp).toLocaleString("en-IN", {
              timeZone: "Asia/Calcutta",
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
              day: "2-digit",
              month: "short",
            })}
          </time>
        </div>
      ))}
      {!list.length && (
        <div className="empty">No audit events match this view.</div>
      )}
    </div>
  );
}
