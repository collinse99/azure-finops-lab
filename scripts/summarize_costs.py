import argparse
import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

GROUPS = {
    "by-date": "date",
    "by-resource-group": "resourceGroupName",
    "by-service": "meterCategory",
    "by-resource": "ResourceId",
}

REQUIRED = {
    *GROUPS.values(),
    "billingCurrency",
    "costInBillingCurrency",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports"))
    args = parser.parse_args()

    totals = defaultdict(Decimal)
    summaries = {
        name: defaultdict(Decimal)
        for name in GROUPS
    }
    row_count = 0

    with args.input.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.reader(source)
        header = next(reader, None)

        if not header:
            raise ValueError("CSV is empty: no header found.")

        if len(header) != len(set(header)):
            raise ValueError("CSV contains duplicate column names.")

        missing = REQUIRED - set(header)
        if missing:
            raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

        for line_number, values in enumerate(reader, start=2):
            if not values:
                continue

            if len(values) != len(header):
                raise ValueError(
                    f"Line {line_number}: expected {len(header)} fields, "
                    f"found {len(values)}."
                )

            row = dict(zip(header, values))
            currency = row["billingCurrency"].strip()
            if not currency:
                raise ValueError(f"Line {line_number}: missing currency.")

            try:
                cost = Decimal(row["costInBillingCurrency"].strip())
            except InvalidOperation:
                raise ValueError(
                    f"Line {line_number}: invalid cost."
                ) from None

            if not cost.is_finite():
                raise ValueError(f"Line {line_number}: cost must be finite.")

            totals[currency] += cost

            for name, column in GROUPS.items():
                label = row[column].strip() or "Unassigned"
                summaries[name][(currency, label)] += cost

            row_count += 1

    args.output.mkdir(parents=True, exist_ok=True)

    for name, column in GROUPS.items():
        destination = args.output / f"{name}.csv"
        with destination.open("w", newline="", encoding="utf-8") as target:
            writer = csv.writer(target)
            writer.writerow(["billingCurrency", column, "totalCost"])

            ordered = sorted(
                summaries[name].items(),
                key=lambda item: (
                    item[0][0],
                    -item[1],
                    item[0][1],
                ),
            )
            for (currency, label), cost in ordered:
                writer.writerow([currency, label, str(cost)])

    print(f"Processed {row_count} usage rows.")
    for currency, total in sorted(totals.items()):
        print(f"Total: {currency} {total:.2f}")

    if row_count == 0:
        print("Header-only export: no usage data available yet.")

    print(f"Reports saved to {args.output}")


if __name__ == "__main__":
    main()
