# Phase 3C.1 Live Complaint Evidence Test Report

**Run date:** 2026-10-20<br>
**Environment:** Local backend `.venv`, disposable SQLite databases, live Cloudinary API<br>
**Scope:** Synthetic complaint evidence only

## Summary

The live API lifecycle passed. An anonymous complaint with a generated synthetic PNG was submitted through Django while storage was configured for Cloudinary. Cloudinary reported the asset as an authenticated image. The administrator and the complaint's associated vendor could preview it; an anonymous requester and an unrelated vendor were denied. The downloaded bytes matched the generated PNG. A synthetic legacy local evidence file also remained readable through the protected Django endpoint.

The first attempt ran inside the default network sandbox, where DNS was blocked. A bounded SDK ping then passed with network access enabled, and the complete lifecycle was rerun successfully. Both candidate IDs from the attempts were checked afterward and confirmed absent from Cloudinary.

## Results

| Check | Result | Details |
| --- | --- | --- |
| Temporary SQLite database and migrations | **VERIFIED** | Django migrations completed in a disposable SQLite database. Temporary database and files were removed. |
| Development database preserved | **VERIFIED# Phase 3C.1 Live Complaint Evidence Test Report

**Run date:** 2026-10-20
**Environment:** Local backend `.venv`, disposable SQLite databases, live Cloudinary API
**Scope:** Synthetic complaint evidence only

## Summary

The live API lifecycle passed. An anonymous complaint with a generated synthetic PNG was submitted through Django while storage was configured for Cloudinary. Cloudinary reported the asset as an authenticated image. The administrator and the complaint's associated vendor could preview it; an anonymous requester and an unrelated vendor were denied. The downloaded bytes matched the generated PNG. A synthetic legacy local evidence file also remained readable through the protected Django endpoint.

The first attempt ran inside the default network sandbox, where DNS was blocked. A bounded SDK ping then passed with network access enabled, and the complete lifecycle was rerun successfully. Both candidate IDs from the attempts were checked afterward and confirmed absent from Cloudinary.

## Results

| Check | Result | Details |
| --- | --- | --- |
| Temporary SQLite database and migrations | **VERIFIED** | Django migrations completed in a disposable SQLite database. Temporary database and files were removed. |
| Development database preserved | **VERIFIED** | Django was redirected to a temporary database before setup; the development database was not selected or migrated. |
| Cloudinary settings loaded | **VERIFIED** | Backend resolved `DOCUMENT_STORAGE_BACKEND=cloudinary` and `DOCUMENT_PROCESSING_MODE=manual`. Cloud name, API key, and API secret were each present; values were never printed. |
| Official Cloudinary SDK connectivity | **VERIFIED** | Authenticated SDK ping succeeded with a bounded timeout. |
| Synthetic administrator/vendor JWT login | **VERIFIED** | Temporary administrator and vendor accounts logged in through the local API. |
| Public anonymous complaint submission with PNG | **VERIFIED** | The complaint API returned success and linked the supplied synthetic vendor. |
| Cloudinary storage key and folder | **VERIFIED** | The saved key used `cloudinary/epalengke_complaints/` and a random asset identifier. |
| Authenticated Cloudinary delivery | **VERIFIED** | Cloudinary resource lookup returned the expected image resource with delivery type `authenticated`. |
| Administrator preview | **VERIFIED** | Protected Django evidence endpoint returned HTTP 200 and matching PNG bytes. |
| Associated-vendor preview | **VERIFIED** | The vendor linked to the complaint received HTTP 200 and matching PNG bytes. |
| Anonymous evidence denial | **VERIFIED** | Unauthenticated request was denied. |
| Unrelated-vendor evidence denial | **VERIFIED** | A different vendor received HTTP 404. |
| Downloaded-file integrity | **VERIFIED** | Administrator download returned attachment content matching the original generated PNG byte-for-byte. |
| Cloudinary URL exposure | **VERIFIED** | Create and detail API responses exposed the Django-protected evidence endpoint, not a Cloudinary delivery URL. |
| Legacy local evidence access | **VERIFIED (synthetic fixture)** | A legacy-path local file was served through the administrator endpoint with matching bytes. This validates the compatibility path, not every pre-existing record individually. |
| Cloudinary test asset cleanup | **VERIFIED** | The exact successful-run asset ID was checked after cleanup and Cloudinary returned `NotFound`. The earlier sandbox-blocked attempt's exact candidate was also checked and returned `NotFound`. No folder or prefix deletion was used. |
| Temporary database and media cleanup | **VERIFIED** | Disposable SQLite and media directories were removed. |

## Test asset identifiers

The two generated identifiers were queried individually after the run and confirmed absent:

- `epalengke_complaints/ca685a4b93c442c6b91f738279b60707` — successful lifecycle test asset, deleted and verified absent.
- `epalengke_complaints/a7e7f3bee92643868209147e9e1c0226` — first attempt did not receive an API response; exact-ID lookup confirmed absent.

These random IDs contain no complainant or vendor information. No other assets were targeted.

## Security and data handling

- Test users, vendor profile, complaint, and PNG were synthetic and existed only in temporary SQLite/media paths.
- Cloudinary credentials and account details were not printed or included in this report.
- Complaint evidence remained behind the authenticated Django endpoint; the frontend-facing response did not include a Cloudinary delivery URL.
- Local evidence compatibility was exercised using a synthetic fixture only. Existing real evidence records were not read, copied, or modified.
- No production service was contacted or changed.

## Browser and production behavior

- **Browser behavior: NOT TESTED.** This was an API-level test using Django REST Framework's test client; no browser UI was exercised.
- **Production behavior: NOT TESTED.** No PythonAnywhere or Vercel service was contacted or changed.
- **Maintained test suite: NOT RUN as part of this live test.** This run targeted the real Cloudinary lifecycle; prior automated Phase 3C.1 tests are documented separately.

## Readiness assessment

**Ready for a dummy complaint-evidence upload in the local environment.** The API-level upload, authenticated delivery, access rules, byte integrity, and exact-asset cleanup all passed. Browser UI behavior and production configuration still require separate acceptance checks before pilot use.
** | Django was redirected to a temporary database before setup; the development database was not selected or migrated. |
| Cloudinary settings loaded | **VERIFIED** | Backend resolved `DOCUMENT_STORAGE_BACKEND=cloudinary` and `DOCUMENT_PROCESSING_MODE=manual`. Cloud name, API key, and API secret were each present; values were never printed. |
| Official Cloudinary SDK connectivity | **VERIFIED** | Authenticated SDK ping succeeded with a bounded timeout. |
| Synthetic administrator/vendor JWT login | **VERIFIED** | Temporary administrator and vendor accounts logged in through the local API. |
| Public anonymous complaint submission with PNG | **VERIFIED** | The complaint API returned success and linked the supplied synthetic vendor. |
| Cloudinary storage key and folder | **VERIFIED** | The saved key used `cloudinary/epalengke_complaints/` and a random asset identifier. |
| Authenticated Cloudinary delivery | **VERIFIED** | Cloudinary resource lookup returned the expected image resource with delivery type `authenticated`. |
| Administrator preview | **VERIFIED** | Protected Django evidence endpoint returned HTTP 200 and matching PNG bytes. |
| Associated-vendor preview | **VERIFIED** | The vendor linked to the complaint received HTTP 200 and matching PNG bytes. |
| Anonymous evidence denial | **VERIFIED** | Unauthenticated request was denied. |
| Unrelated-vendor evidence denial | **VERIFIED** | A different vendor received HTTP 404. |
| Downloaded-file integrity | **VERIFIED** | Administrator download returned attachment content matching the original generated PNG byte-for-byte. |
| Cloudinary URL exposure | **VERIFIED** | Create and detail API responses exposed the Django-protected evidence endpoint, not a Cloudinary delivery URL. |
| Legacy local evidence access | **VERIFIED (synthetic fixture)** | A legacy-path local file was served through the administrator endpoint with matching bytes. This validates the compatibility path, not every pre-existing record individually. |
| Cloudinary test asset cleanup | **VERIFIED** | The exact successful-run asset ID was checked after cleanup and Cloudinary returned `NotFound`. The earlier sandbox-blocked attempt's exact candidate was also checked and returned `NotFound`. No folder or prefix deletion was used. |
| Temporary database and media cleanup | **VERIFIED** | Disposable SQLite and media directories were removed. |

## Test asset identifiers

The two generated identifiers were queried individually after the run and confirmed absent:

- `epalengke_complaints/ca685a4b93c442c6b91f738279b60707` — successful lifecycle test asset, deleted and verified absent.
- `epalengke_complaints/a7e7f3bee92643868209147e9e1c0226` — first attempt did not receive an API response; exact-ID lookup confirmed absent.

These random IDs contain no complainant or vendor information. No other assets were targeted.

## Security and data handling

- Test users, vendor profile, complaint, and PNG were synthetic and existed only in temporary SQLite/media paths.
- Cloudinary credentials and account details were not printed or included in this report.
- Complaint evidence remained behind the authenticated Django endpoint; the frontend-facing response did not include a Cloudinary delivery URL.
- Local evidence compatibility was exercised using a synthetic fixture only. Existing real evidence records were not read, copied, or modified.
- No production service was contacted or changed.

## Browser and production behavior

- **Browser behavior: NOT TESTED.** This was an API-level test using Django REST Framework's test client; no browser UI was exercised.
- **Production behavior: NOT TESTED.** No PythonAnywhere or Vercel service was contacted or changed.
- **Maintained test suite: NOT RUN as part of this live test.** This run targeted the real Cloudinary lifecycle; prior automated Phase 3C.1 tests are documented separately.

## Readiness assessment

**Ready for a dummy complaint-evidence upload in the local environment.** The API-level upload, authenticated delivery, access rules, byte integrity, and exact-asset cleanup all passed. Browser UI behavior and production configuration still require separate acceptance checks before pilot use.
