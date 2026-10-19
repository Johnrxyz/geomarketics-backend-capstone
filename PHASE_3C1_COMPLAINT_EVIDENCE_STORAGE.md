# Phase 3C.1 — Secure Complaint Evidence Storage

## 1. Existing architecture

Complaint records use `Complaint.evidence_file`, a Django `FileField`. Before this phase, the field used Django's global default storage and the serializers returned its file URL directly. Depending on environment settings, that meant local media storage or the general Cloudinary media backend, which can expose a direct delivery URL.

Complaint creation remains public. Authenticated administrators can view all complaints, customers can view complaints linked to their account, and vendors can view complaints tied to their vendor profile. The vendor complaint screen also supports complaints filed by the signed-in vendor; the queryset now includes those owner-linked records while preserving the vendor serializer's complainant-identity omissions.

## 2. Implementation

- Reused `PrivateDocumentStorage` and `CloudinaryDocumentStorage`; new complaint evidence uses the separate `epalengke_complaints` folder and the same `DOCUMENT_STORAGE_BACKEND=local|cloudinary` setting.
- Cloudinary uploads use authenticated delivery, `image` resource type, a random UUID asset ID, and the original validated extension. Local complaint uploads also receive random filenames. Complainant names and original filenames are not used in stored asset identifiers.
- The shared upload validator accepts PDF, JPG/JPEG, and PNG files, checks their signatures, and applies the existing 10 MB limit.
- Existing local evidence stored under `MEDIA_ROOT/complaints/` remains readable through the private storage adapter. New local evidence is written under `PRIVATE_DOCUMENT_ROOT`. Existing records and files are not migrated or deleted.
- Complaint serializers return `/api/v1/complaints/{id}/evidence/` instead of a media or Cloudinary URL.
- Evidence retrieval requires authentication and allows administrators, the linked complainant account, and the vendor associated with the complaint. Other vendors receive no access. Anonymous complaint submission remains enabled, while anonymous retrieval is denied.
- Evidence responses are served by Django with `private, no-store`, `nosniff`, and inline/download disposition headers. Legacy `/media/complaints/...` requests return 404.
- Complaint creation and its database notification writes run in a transaction. If that transaction rolls back after storage succeeds, the uploaded file is removed on a best-effort basis. Storage failures return HTTP 503 and do not switch to public or local storage. Existing SMS handling remains after the database transaction.
- Admin and vendor complaint screens use authenticated blob retrieval for evidence previews. Existing public and vendor forms keep their current flow and show only supported file types in the picker.

### Authorization decisions

| Requester | Evidence access |
| --- | --- |
| Administrator | Any complaint |
| Authenticated complainant | Their own account-linked complaint |
| Vendor | Complaint linked to their vendor profile, or filed by their account |
| Unrelated vendor/customer | Denied |
| Anonymous visitor | Denied |

Publicly filed anonymous complaints have no complainant account owner. Administrators and the vendor associated with the complaint can view their evidence through authenticated endpoints.

## 3. Changed files

Backend:

- `apps/documents/storage.py` — reusable folder-specific private storage and complaint storage instance.
- `apps/documents/services/upload_validation.py` — reusable field-specific validation errors.
- `apps/complaints/models.py` — complaint evidence uses private storage.
- `apps/complaints/serializers.py` — validates uploads and returns protected evidence routes.
- `apps/complaints/views.py` — evidence authorization, protected response, atomic create and cleanup, and owner-aware vendor queryset.
- `apps/complaints/tests.py` — local, Cloudinary-mocked, authorization, validation, legacy access, and rollback coverage.
- `apps/complaints/migrations/0007_alter_complaint_evidence_file.py` — storage-state migration; it does not change complaint records or copy files.
- `core/urls.py` — blocks public media serving for legacy complaint evidence.

Frontend:

- `lib/api.ts` — authenticated complaint evidence fetch.
- `components/complaints/ComplaintEvidenceButton.tsx` — protected preview control and upload access error feedback.
- `app/admin/complaints/page.tsx`, `app/complaints/page.tsx`, and `app/vendor/complaints/page.tsx` — protected previews.
- `app/page.tsx` — public complaint file picker accepts supported image formats.

## 4. Test results

All maintained backend test modules were run against Django's temporary test database with `DOCUMENT_STORAGE_BACKEND=local`; Cloudinary-specific tests use mocks.

- **89 maintained Django tests passed.** This includes 27 complaint-focused tests.
- **Django system check:** passed, no issues.
- **Migration consistency (`makemigrations --check --dry-run`):** passed, no model changes pending.
- **Frontend TypeScript (`npx tsc --noEmit`):** passed.
- **Frontend production build (`npm run build`):** passed.
- The complaint-focused tests cover Cloudinary-mocked PNG/JPG/PDF uploads, authenticated retrieval, legacy local retrieval, anonymous and cross-user denials, validation, provider failure, and rollback cleanup.
- No production database, PythonAnywhere service, or real Cloudinary asset was changed by these checks.

The maintained suite was invoked with explicit app test modules. The repository also contains standalone network scripts and `apps/documents/services/test_rest.py`, which make outbound requests at import time and are not maintained Django tests; they were excluded. The full discovery attempt was not used as the final result because it also picks up those scripts.

## 5. Security observations and remaining limitations

- No permanent Cloudinary URL is returned in complaint API responses. Cloudinary's short-lived private delivery URL is generated and consumed server-side after Django authorization.
- Anonymous complaint submission may upload evidence, but the create response's evidence route does not grant anonymous read access.
- Existing local evidence is not copied to Cloudinary. Legacy local media must remain available under the configured `MEDIA_ROOT` for the private adapter to serve it.
- If older evidence was previously stored in Cloudinary through the former general media backend, its database key may look like a local `complaints/...` path. This implementation does not migrate or delete such assets; those legacy Cloudinary records need a separate inventory before changing storage in production.
- Deleting a complaint continues the prior behavior: Django removes the database row but does not automatically remove the underlying evidence file. This avoids changing deletion behavior or removing existing files, but newly uploaded files can become orphaned after an administrator deletes a complaint.
- Cloudinary rollback cleanup is best-effort. If Cloudinary accepts an upload and both the request and compensating delete fail, a provider asset can remain without a database record. Logs avoid provider exception strings and credentials.
- Automated tests mock Cloudinary. Live Cloudinary upload/retrieval remains untested in this phase.

## 6. Manual acceptance checklist

1. With `DOCUMENT_STORAGE_BACKEND=cloudinary` configured in a local environment, submit a synthetic PNG complaint through the public form.
2. Confirm the API returns a complaint number and an `/api/v1/complaints/{id}/evidence/` URL, with no Cloudinary URL.
3. Confirm the asset appears under `epalengke_complaints` as authenticated delivery and its ID is random.
4. Confirm anonymous access to the evidence endpoint returns 401 and `/media/complaints/...` returns 404.
5. Sign in as an administrator and confirm the evidence preview opens.
6. Sign in as the complainant account and confirm only that account can retrieve its complaint evidence.
7. Sign in as the complaint's vendor and confirm it can access the evidence; use a different vendor account to confirm access is denied.
8. Repeat with a JPG, PNG, and PDF; verify unsupported extensions, mismatched signatures, and files over 10 MB show a validation error.
9. Temporarily disable Cloudinary credentials or simulate an upload failure and confirm submission reports a storage error without a local/public fallback.
10. Confirm a legacy local evidence file remains viewable through the protected endpoint.

## 7. Deployment considerations

- Back up the PythonAnywhere SQLite database before release.
- Configure `DOCUMENT_STORAGE_BACKEND=cloudinary` and the existing Cloudinary credentials in the PythonAnywhere backend environment. Do not put secrets in Vercel variables or frontend code.
- Deploy the backend code and run `python manage.py migrate complaints` against the intended deployment database. Migration `0007` changes the recorded storage class only and does not migrate files or alter complaint rows.
- Deploy the frontend changes alongside the backend endpoint so complaint screens use authenticated previews.
- Keep existing local media files in their current `MEDIA_ROOT`; this phase does not copy them to Cloudinary.
- Verify public upload, administrator preview, owner access, unrelated-vendor denial, anonymous denial, and legacy local preview after deployment. PythonAnywhere deployment and reload were not performed.
