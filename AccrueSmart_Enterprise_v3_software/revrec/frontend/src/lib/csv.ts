export type CSVParseResult<T> =
  | { ok: true; rows: T[]; headers: string[] }
  | { ok: false; error: string };

function normalizeCsvText(raw: string): string {
  let text = raw.replace(/^\uFEFF/, "").trim(); // strip BOM + trim

  if (!text) return "";

  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  // Handle your exact bad format:
  // "label,period,amount,reversal_year,va_pct"
  // "Depreciation,2025-12,10000,2026,0"
  const normalized = lines.map((line) => {
    const isWrappedQuoted = line.startsWith('"') && line.endsWith('"');
    if (isWrappedQuoted && line.includes(",")) {
      return line.slice(1, -1); // unwrap
    }
    return line;
  });

  return normalized.join("\n");
}

// Minimal CSV split (good for your simple numeric/text CSV, not for complex quoted embedded commas)
function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];

    if (ch === '"') {
      // escaped quote
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (ch === "," && !inQuotes) {
      out.push(cur.trim());
      cur = "";
      continue;
    }

    cur += ch;
  }

  out.push(cur.trim());
  return out;
}

export function parseTempDiffCsv(
  raw: string,
  options?: {
    requireLabel?: boolean;
    requireRowVAPct?: boolean;
    defaultVaPct?: number;
  }
): CSVParseResult<Array<Record<string, any>>> {
  const requireLabel = options?.requireLabel ?? true;
  const requireRowVAPct = options?.requireRowVAPct ?? false;
  const defaultVaPct = options?.defaultVaPct ?? 0;

  const text = normalizeCsvText(raw);
  if (!text) return { ok: false, error: "CSV file is empty." };

  const lines = text.split(/\r?\n/).filter(Boolean);
  if (!lines.length) return { ok: false, error: "CSV file is empty." };

  const headers = splitCsvLine(lines[0]).map((h) => h.trim());
  const lowerHeaders = headers.map((h) => h.toLowerCase());

  const required = ["period", "amount", "reversal_year"];
  if (requireLabel) required.unshift("label");
  if (requireRowVAPct) required.push("va_pct");

  const missing = required.filter((h) => !lowerHeaders.includes(h));
  if (missing.length) {
    return {
      ok: false,
      error:
        `Missing required headers: ${missing.join(", ")}.\n` +
        `Required headers: ${required.join(", ")}.\n` +
        `Optional: va_pct`,
    };
  }

  const rows: Array<Record<string, any>> = [];

  for (let i = 1; i < lines.length; i++) {
    const vals = splitCsvLine(lines[i]);
    if (vals.every((v) => !String(v).trim())) continue;

    const row: Record<string, any> = {};
    headers.forEach((h, idx) => {
      row[h.toLowerCase()] = (vals[idx] ?? "").trim();
    });

    try {
      const parsed = {
        label: (row.label || "Unlabeled Temp Difference").toString().trim(),
        period: String(row.period || "").trim(),
        amount: Number(row.amount),
        reversal_year: Number(row.reversal_year),
        va_pct:
          row.va_pct === undefined || row.va_pct === ""
            ? defaultVaPct
            : Number(row.va_pct),
      };

      if (!parsed.period) throw new Error("period is blank");
      if (Number.isNaN(parsed.amount)) throw new Error("amount is not a number");
      if (!Number.isFinite(parsed.reversal_year))
        throw new Error("reversal_year is not a number");
      if (Number.isNaN(parsed.va_pct)) throw new Error("va_pct is not a number");
      if (parsed.va_pct < 0 || parsed.va_pct > 1)
        throw new Error("va_pct must be between 0 and 1");

      rows.push(parsed);
    } catch (e: any) {
      return { ok: false, error: `Row ${i + 1}: ${e.message}` };
    }
  }

  if (!rows.length) {
    return { ok: false, error: "CSV has headers but no data rows." };
  }

  return { ok: true, rows, headers };
}
