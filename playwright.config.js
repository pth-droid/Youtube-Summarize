const {defineConfig} = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests_app/browser',
  timeout: 45000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', {open: 'never'}]],
  use: {baseURL: 'http://127.0.0.1:8766', headless: true, trace: 'retain-on-failure'},
  webServer: {
    command: '.venv\\Scripts\\python.exe -m tests_app.browser_server',
    url: 'http://127.0.0.1:8766/api/health',
    reuseExistingServer: false,
    timeout: 30000,
  },
});
