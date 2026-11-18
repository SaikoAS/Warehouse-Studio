# Synthetic CSV examples

Import each example into a separate project with **Use the first CSV row** selected. All records and identifiers are fictional. The CSV line shown in each table is the physical line where the original record starts, including when a quoted value spans multiple lines.

## [csv-valid.csv](csv-valid.csv)

1. Rename the source column `Quantity` to `Prepared quantity`.
2. Keep exact matches for `Keep` in `Kind`.
3. Convert the source column `Quantity` to Decimal using German (Germany).

The first preview includes all three records and the new column name. The second preview contains two records with their original decimal commas. The third preview and the saved result contain these rows.

| CSV line | Article (Text) | Kind (Text) | Prepared quantity (Decimal) | Note (Text) |
| --- | --- | --- | --- | --- |
| 2 | `0007` | `Keep` | `12.50` | `Synthetic; "quoted"` |
| 4 | `0042` | `Keep` | `-0.075` | `Two` followed by a line break and `fixture lines` |

Reopen the project and run Apply again. The saved steps and the resulting values should match. Moving conversion before the filter should cause an error at CSV line 3, column 3 (`Quantity`).

## [csv-invalid-decimal.csv](csv-invalid-decimal.csv)

Rename `Quantity` to `Prepared quantity` and convert the source column `Quantity` to **Text**. Select **Apply** to save both rows with the values `1,50` and `not-a-number`. Change the second step to Decimal and select German (Germany). Both its preview and Apply should report `Step 2: invalid decimal at CSV line 4, column 3 (Quantity).` The previously saved steps, result and original bytes should be identical after the failed Apply.

[Runtime tests](../test_preparation.py) exercise both files and generate a CSV of exactly 1,048,576 bytes to verify the initial import limit. They also verify rejection at 1,048,577 bytes.
