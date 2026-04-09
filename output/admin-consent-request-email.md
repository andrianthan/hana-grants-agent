# Email: Request for Azure AD Admin Consent

**To:** [IT Admin / Microsoft 365 Administrator]
**From:** Andrian Than
**Subject:** Action Needed: Grant admin consent for Hanna Grants Agent app (5 minutes)

---

Hi [Name],

I'm building an internal tool called **Hanna Grants Agent** that automatically finds and scores grant opportunities for Hanna Center. It needs to write scored grants to a shared Excel workbook in OneDrive so the development team can review and approve them.

To connect to our OneDrive/SharePoint, I've registered an app in Azure AD called **Hanna Grants Agent**, but it needs admin consent for two Microsoft Graph permissions:

- **Files.ReadWrite.All** — so it can write grant data to an Excel file in OneDrive
- **Sites.ReadWrite.All** — so it can access the shared site where the file lives

**What I need from you:** Grant admin consent for this app. It takes about 2 minutes — I've attached a step-by-step guide.

**Quick details:**
- App name: Hanna Grants Agent
- App ID: 2827d637-680e-42dc-ab2d-fdd9e85a11fd
- What it does: Writes scored grant opportunities to a shared Excel workbook daily
- What it does NOT do: It does not access email, calendar, or any user data

Please let me know if you have any questions. Happy to walk through it together if that's easier.

Thanks,
Andrian
