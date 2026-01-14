/**
 * Puppeteer configuration for mermaid-cli in CI environments
 * 
 * This configuration adds the --no-sandbox flag which is required
 * when running Chromium in containerized environments like GitHub Actions.
 * 
 * These flags are safe to use in CI because:
 * - CI runners are already isolated containers
 * - The sandbox is redundant in these environments
 * - It prevents "No usable sandbox!" errors on Ubuntu 23.10+
 */

module.exports = {
  launch: {
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu'
    ]
  }
};
