# How to Grant Admin Consent for Hanna Grants Agent

**Time required:** ~2 minutes
**Who can do this:** Microsoft 365 Global Administrator or Privileged Role Administrator

---

## Option A: One-Click Consent URL (Fastest)

1. Open this URL in your browser while signed in as an admin:

```
https://login.microsoftonline.com/60791775-2126-4012-80bb-e162cc58cd45/adminconsent?client_id=2827d637-680e-42dc-ab2d-fdd9e85a11fd
```

2. Sign in with your admin account if prompted
3. Review the permissions and click **Accept**
4. Done. You'll be redirected to a confirmation page.

---

## Option B: Via Azure Portal

1. Go to https://entra.microsoft.com
2. Sign in with your admin account
3. In the left sidebar, click **Applications** → **App registrations**
4. Click **Hanna Grants Agent** in the list
5. In the left sidebar, click **API permissions**
6. You'll see this:

   | Permission | Type | Status |
   |-----------|------|--------|
   | Files.ReadWrite.All | Application | Not granted |
   | Sites.ReadWrite.All | Application | Not granted |

7. Click the blue button: **Grant admin consent for Hanna Center**
8. Click **Yes** to confirm
9. The status should change to green checkmarks: **Granted for Hanna Center**

---

## What These Permissions Do

| Permission | What it allows | What it does NOT allow |
|-----------|---------------|----------------------|
| Files.ReadWrite.All | Read and write files in OneDrive/SharePoint | No access to email, calendar, or Teams |
| Sites.ReadWrite.All | Access SharePoint sites to find the shared Excel file | No access to user profiles or personal data |

The app uses these permissions solely to write scored grant opportunities to a shared Excel workbook that the development team reviews.

---

## Security Notes

- **App ID:** 2827d637-680e-42dc-ab2d-fdd9e85a11fd
- **Tenant:** Hanna Center (60791775-2126-4012-80bb-e162cc58cd45)
- **Single tenant only** — this app cannot be used by other organizations
- The app runs on AWS Lambda and authenticates using a client secret stored in AWS Secrets Manager
- No user passwords or personal data are accessed

---

## After Granting Consent

Let Andrian know it's done — no further action needed from you. The app will start writing grant data to the shared Excel workbook automatically.

## Questions?

Contact Andrian Than (athan@hannacenter.org)
