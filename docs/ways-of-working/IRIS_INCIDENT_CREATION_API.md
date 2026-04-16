# IRIS Incident Creation API Spike (2026-04-16)

This note captures the confirmed case-creation contract from the bundled DFIR-IRIS source (`v2.4.27`) used in this repo.

## Confirmed Endpoint

- Route: `POST /manage/cases/add`
- Source: `.vendor/iris-web/source/app/blueprints/manage/manage_cases_routes.py`
- Handler: `api_add_case()` calling `create(request.get_json())`

## Required Request Fields

Based on `CaseSchema` in `.vendor/iris-web/source/app/schema/marshables.py`:

- `case_name` (string, required, min length 2)
- `case_description` (string, required, min length 2)
- `case_soc_id` (required)
- `case_customer` (int, required; valid existing client)

## Supported Optional Fields

- `case_tags` (string)
- `classification_id` (int)
- `severity_id` (int)
- `case_template_id` (string/int; consumed before schema load)
- `custom_attributes` (object)

## Expected Response Shape

The route uses `response_success(..., data=case_schema.dump(case))`, so response envelope is:

```json
{
  "status": "success",
  "message": "Case created",
  "data": {
    "case_id": 123,
    "case_name": "#123 - ...",
    "case_description": "...",
    "case_soc_id": "...",
    "case_customer": 1
  }
}
```

## Implementation Decisions for UniOps

- Use `POST /manage/cases/add` as primary create endpoint.
- Keep `/api/ingest/iris` read-only (fetch existing case only).
- Expose explicit create endpoint: `POST /api/incidents/create` in backend.
- Add approval-driven creation path via executor tool `iris.create_incident`.
