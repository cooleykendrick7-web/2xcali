# 2xcali — Get on the List

Live funnel for 2xcali's EP "1502". Fans sign up with name / email / phone.
Leads are saved to a persistent SQLite database on Render (/data/leads.db).

- Site: `/`
- Thank-you: `/success.html`
- Admin leads board: `/admin` (password protected, ADMIN_PASSWORD env var on Render)
- Leads JSON: `/api/leads?key=ADMIN_PASSWORD`
- Signup API: `POST /api/signup`

Deploy: GitHub repo → Render Blueprint (Starter, persistent disk).
