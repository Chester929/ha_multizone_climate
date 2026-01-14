# Workflow Testing Guide

## Testing the PDF Generation Workflow

### Prerequisites
- Workflow file: `.github/workflows/generate-diagrams-pdf.yml`
- Target file: `DIAGRAMS.md`

### How the Workflow is Triggered

#### Automatic Trigger
The workflow automatically runs when:
1. A commit is pushed to `master` or `dev` branch
2. The commit includes changes to `DIAGRAMS.md`

#### Manual Trigger
You can manually trigger the workflow:
1. Go to GitHub repository → **Actions** tab
2. Select **Generate Diagrams PDF** workflow
3. Click **Run workflow** button
4. Select branch (master/dev)
5. Click **Run workflow**

### Workflow Steps

1. **Checkout repository** - Gets the latest code
2. **Setup Node.js** - Installs Node.js v20
3. **Install mermaid-cli** - Installs `@mermaid-js/mermaid-cli` as a local dependency (used via `npx`)
4. **Generate PDF** - Runs `npx mmdc -i DIAGRAMS.md -o diagrams.pdf -t dark -b transparent`
5. **Upload artifact** - Uploads `diagrams.pdf` as artifact (90-day retention)
6. **Validate PDF** - Checks if PDF exists and has content (non-blocking)
7. **Commit PDF** - Commits the generated PDF back to the repository (with `[skip ci]`)

### Accessing Generated PDFs

#### Option 1: GitHub Actions Artifacts
1. Go to **Actions** tab
2. Click on the workflow run
3. Scroll to **Artifacts** section
4. Download `diagrams-pdf`

#### Option 2: Repository (if committed)
- The PDF will be committed to the repository as `diagrams.pdf`
- Access it directly from the repository root

### Testing Locally

To test PDF generation locally:

```bash
# Install mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# Generate PDF
mmdc -i DIAGRAMS.md -o diagrams.pdf -t dark -b transparent

# Verify output
ls -lh diagrams.pdf
```

### Troubleshooting

#### Workflow doesn't trigger
- Ensure changes are pushed to `master` or `dev` branch
- Verify `DIAGRAMS.md` was actually modified in the commit

#### PDF generation fails
- Check Actions logs for error messages
- Verify DIAGRAMS.md has valid Mermaid syntax
- Check for rate limits or network issues

#### PDF not committed
- Verify the workflow has write permissions
- Check if there were actual changes to the PDF
- Look for errors in the "Commit and push PDF" step

### Workflow Features

- **Dark theme**: Uses dark theme for professional appearance
- **Transparent background**: PDF has transparent background
- **Skip CI tag**: Commits use `[skip ci]` to prevent infinite loops
- **Artifact retention**: PDFs are kept for 90 days
- **Conditional commit**: Only commits if PDF actually changed

### File Permissions

The workflow requires:
- **Read**: To checkout code
- **Write**: To commit PDF back to repository
- **Actions**: To upload artifacts

These are typically granted by default with `GITHUB_TOKEN`.
