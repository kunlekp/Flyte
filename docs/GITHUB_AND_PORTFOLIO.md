# Putting Flyte on GitHub (for both of you) and setting up your portfolios

Do these in order. Steps marked **Owner** are done by whoever publishes the repository;
**Partner** is the other person. **Both** means each of you, on your own account.

Before you start, swap these details:
- each other's **GitHub username**;
- each other's **commit email**: GitHub → Settings → Emails. If "Keep my email address private" is on,
  use the address shown there, e.g. `12345678+username@users.noreply.github.com`.

---

## Part 1: Publish the project with credit for both of you

1. **Owner:** open the `flyte` folder in VS Code.
2. **Owner:** in the terminal, set your identity once:
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "your-github-email"
   ```
3. **Owner:** in the README, fill in the **Authors** section near the bottom (both names and GitHub links).
4. **Owner:** open Source Control (Ctrl+Shift+G) → **Initialize Repository**. Type this commit message
   (the empty line matters), then click **✓ Commit** and **Yes** to stage everything:
   ```
   Flyte: airline booking and analytics web app

   Co-authored-by: Partner Name <partner-github-email>
   ```
5. **Owner:** click **Publish Branch** → sign in → choose **Public**.
6. **Owner:** on GitHub open the repo → the latest commit should show **both** profile pictures.
   If only yours shows, the partner's email in the `Co-authored-by` line doesn't match their account.
7. **Owner:** repo **Settings → Collaborators → Add people** → the partner's username.
8. **Partner:** accept the invitation from your email or github.com/notifications.
9. **Partner:** make at least one commit of your own (for example, fill in your "What I did" lines in the
   README). Clone it in VS Code: Ctrl+Shift+P → **Git: Clone** → paste the repo URL → edit →
   commit → **Sync Changes**.
10. **Both:** on your GitHub profile → **Customize your pins** → tick `flyte`. You can pin it because you
    have both contributed to it.

From now on, when you work on something together, add the same `Co-authored-by:` line to the commit.

### Other route: the repo lives on the partner's account, but you push from your computer

Use this when the repository should belong to one person (say, the student) but the other person has the
code on their machine.

1. **Repo owner (on their GitHub account):** **New repository** → name `flyte` → **Public** → leave
   *Add a README*, *.gitignore* and *license* **unticked** (it must be empty) → **Create repository**.
2. **Repo owner:** **Settings → Collaborators → Add people** → the other person's username.
3. **You:** accept the invitation (email or github.com/notifications).
4. **You, in VS Code** with the `flyte` folder open, in the terminal:
   ```bash
   git init
   git branch -M main
   git add .
   git commit -m "Flyte: airline booking and analytics web app" -m "Co-authored-by: Owner Name <owner-github-email>"
   git remote add origin https://github.com/OWNER-USERNAME/flyte.git
   git push -u origin main
   ```
   Sign in with **your own** GitHub account when asked. Being a collaborator gives you permission to push.
5. Refresh the repo page: all the files appear, and the commit shows both profile pictures.

The repo belongs to the owner. As a collaborator you can push, and you can pin it on your profile once you
have commits in it, but you can't delete it, rename it or change its settings.

---

## Part 2: A portfolio website for each of you (free, on GitHub Pages)

**Easiest way: the Portfolio Lab maker (`portfolio/maker.html`).** Open it in a browser and fill in your
photo, about me, projects, skills and links. Press **Remix** until you like the design, then **Copy website
code**. Create a public repo named `YOUR-USERNAME.github.io`, choose **Add file → Create new file**, name it
`index.html`, paste and commit. Every remix is a different design, so no two students' sites look the same.
To give students the maker itself, upload `maker.html` to your own `YOUR-USERNAME.github.io` repo. They then
open `https://YOUR-USERNAME.github.io/maker.html`; each person's work saves in their own browser.

The steps below use the simpler hand-edited template (`portfolio/index.html`) instead.

The template is `portfolio/index.html`. All your details live in one block of text at the top of
that file (the part between `<script type="application/json" id="profile">` and `</script>`).

**Both, on your own account:**

1. On GitHub click **New repository**. Name it exactly `YOUR-USERNAME.github.io`, make it **Public**,
   and create it.
2. Click **uploading an existing file** and drag in `index.html` and the `assets` folder from
   `flyte/portfolio/`. Commit.
3. Click `index.html` → the pencil icon. In the block at the top, change:
   - `name`, `role`, `location`, `intro`, `about`;
   - `links`: your GitHub, LinkedIn, email, and CV link if you have one;
   - `featured.contributions`: **what you personally did on Flyte**. This should be different for each of you;
   - `featured.code`: the Flyte repo link; `featured.demo`: the live link once it's deployed;
   - `skills` and `projects`: your own;
   - `accent`: pick your own colour (any hex code) so your two sites don't look identical.
4. Commit. Wait about a minute, then open `https://YOUR-USERNAME.github.io`.
   (If it doesn't appear: repo **Settings → Pages** → Source: *Deploy from a branch* → `main` / `root` → Save.)

Keep the JSON valid: every value in quotes, commas between items, no comma after the last item. If the
page goes blank after an edit, a missing comma or quote is almost always the cause.

## Part 3: Your GitHub profile page

1. Create a **public** repository named exactly your username (GitHub will say *"This is a special repository"*).
2. Tick **Add a README file**, create it, then edit it.
3. Paste `portfolio/PROFILE_README.md`, replace the placeholders and commit. It now shows at the top
   of github.com/YOUR-USERNAME.

## Part 4: Add the live link (optional, after deploying)

When Flyte is live on PythonAnywhere (see `docs/DEPLOYMENT.md`), put the link in:
the Flyte README (top), `featured.demo` in both portfolios, and your profile READMEs.

---

**If this is graded coursework:** check your school's rules on collaboration and on AI tools.
A line in the README saying how the project was built (who did what, and which tools helped) keeps
everything above board.
