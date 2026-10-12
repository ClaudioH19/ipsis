# Inventory retrieval

XLSX, XLS, CSV and TSV are supported alongside the existing document formats.
Load a workbook or a folder with `ipsis load`, then run `ipsis index`. The admin
Documents tab accepts the same formats and lets you reindex them. No training,
LLM or spreadsheet service is required. In v2, the normal output remains up to
three ranked sources, expandable for reading, with search continuation.

```bash
ipsis load ./inventory.xlsx
ipsis index
ipsis serve --demo --open
```

The parser retains a product record as column labels plus the whole data row.
Legacy indexing uses `CH-ROW1` automatically instead of splitting the workbook
by a text chunk budget. Structural indexing uses one parent per record and
searchable data rows; header-only records do not compete as separate results.
Context expansion cannot cross into another product. Source tables use the
existing widget presentation and expose cell coordinates on hover. Offsets
refer to the canonical extracted text, not positions inside the binary file.

| Format | Structure and origin |
|---|---|
| XLSX | All sheets; named Excel tables use their declared ranges and headers. Without tables, the first nonempty row is used as labels with a warning. Notes outside named tables and tables explicitly lacking headers use column coordinates. Source references retain the sheet and cell, such as `'Bodega'!C2`. |
| XLS | All sheets, saved values, first nonempty row as labels with a warning; sheet/cell coordinates. |
| CSV | First nonempty record as labels; comma, semicolon, tab or pipe separator detected. Standard quoted cells can contain separators and line breaks. |
| TSV | Same header contract, with a tab separator. |

CSV/TSV use UTF-8 (including BOM), with a Windows-1252 fallback that emits a
warning. Their row references count logical CSV records; a multiline quoted
cell does not start a new record. Empty columns stay in position, zeros remain
zeros, and text identifiers such as `0007` retain their leading zeros.
Excel's simple integer format `0000` is supported for numeric identifiers.
Dates use ISO text. Currency, percentages and other custom Excel visual formats
are not reproduced; the stored numeric value is shown.

Formula expressions in XLSX are never executed. If a saved result exists, that
value is recovered and the parser warns that it has not been recalculated.
Otherwise the literal formula is retained with a warning. XLS exposes saved
values, without formula expressions. This is retrieval: a request such as
"total stock" does not run an aggregation or infer a newly calculated answer.

Hidden sheets are included and flagged. Merged cells do not copy values into
other product records. Macros and embedded objects are not read. Password
protected files are unsupported. Workbooks must have a clear header row or
declared tables; arbitrary spreadsheet dashboards and multiple undocumented
header regions need preparation before loading. Tables without data are
rejected. A limit of 500,000 cells per sheet (or delimited file) prevents indexing
oversized ranges; split large inventories into smaller files.

`ipsis prepare` also supports these formats in its separate structural copy.
Review its extraction warnings and preview before indexing. The parser version
participates in the index fingerprint for tabular files.
