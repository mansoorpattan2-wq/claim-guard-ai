import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { Claim } from "@/lib/api";
import { Badge, Progress, money } from "./ui";
export default function ClaimTable({ claims: list }: { claims: Claim[] }) {
  return (
    <>
      <div className="table-wrap claims-table">
        <table>
          <thead>
            <tr>
              <th>Claim / beneficiary</th>
              <th>Hospital / procedure</th>
              <th>Claim amount</th>
              <th>Readiness</th>
              <th>Status</th>
              <th>Owner</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.map((c) => (
              <tr key={c.id}>
                <td>
                  <Link className="claim-link" href={"/claims/" + c.id}>
                    {c.id}
                  </Link>
                  <small>{c.patient}</small>
                </td>
                <td>
                  {c.hospital}
                  <small>{c.procedure}</small>
                </td>
                <td className="amount">{money(c.amount)}</td>
                <td>
                  <Progress value={c.readiness} />
                </td>
                <td>
                  <Badge status={c.status} />
                </td>
                <td>
                  <span className="avatar tiny">MS</span>
                  <span className="owner">{c.data.owner}</span>
                </td>
                <td>
                  <Link
                    className="row-action"
                    href={"/claims/" + c.id}
                    aria-label={"Open " + c.id}
                  >
                    <ArrowUpRight size={17} />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {list.length === 0 && (
          <div className="empty">
            No claims match these filters. Try another search or status.
          </div>
        )}
      </div>
      <MobileClaims claims={list} />
    </>
  );
}
function MobileClaims({ claims }: { claims: Claim[] }) {
  return (
    <div className="mobile-claims">
      {claims.map((c) => (
        <Link href={"/claims/" + c.id} key={c.id} className="mobile-claim">
          <div>
            <strong>{c.id}</strong>
            <Badge status={c.status} />
          </div>
          <p>
            {c.patient} ? {c.hospital}
          </p>
          <small>{c.procedure}</small>
          <div className="mobile-claim-score">
            <Progress value={c.readiness} />
            <span>{money(c.amount)}</span>
            <ArrowUpRight size={16} />
          </div>
        </Link>
      ))}
      {!claims.length && <div className="empty">No matching claims.</div>}
    </div>
  );
}
