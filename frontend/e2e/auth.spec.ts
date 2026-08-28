import {
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  expect,
  loginAs,
  logout,
  test,
  uniqueSuffix,
} from './fixtures/app';
import { expectNoSeriousA11yViolations } from './fixtures/axe';

test.describe('authentication', () => {
  test('login page is accessible and rejects invalid credentials', async ({ page }) => {
    await page.goto('/login');
    await expectNoSeriousA11yViolations(page);

    await page.getByLabel('Email').fill(ADMIN_EMAIL);
    await page.getByLabel('Contraseña').fill('definitely-wrong-password');
    await page.getByRole('button', { name: 'Entrar' }).click();

    await expect(page.getByRole('alert')).toHaveText('Email o contraseña incorrectos');
    await expect(page.getByLabel('Email')).toHaveValue(ADMIN_EMAIL);
  });

  test('login succeeds, survives a reload and logs out', async ({ page }) => {
    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expectNoSeriousA11yViolations(page);

    await page.reload();
    await expect(page.getByRole('heading', { name: /^Hoy/, level: 1 })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Entrar en Quermed CRM' })).toHaveCount(0);

    await logout(page);
    await page.goto('/hoy');
    await expect(page).toHaveURL(/\/login\?next=%2Fhoy/);
  });

  test('account locks after ten failed attempts', async ({ page, api }) => {
    const email = `lock-${uniqueSuffix()}@quermed.com`;
    await api.createUser({
      email,
      full_name: 'Lock Test',
      role: 'sales_rep',
      password: 'lock-test-passphrase',
    });

    await page.goto('/login');
    for (let attempt = 0; attempt < 10; attempt += 1) {
      await page.getByLabel('Email').fill(email);
      await page.getByLabel('Contraseña').fill('wrong-password-xx');
      await page.getByRole('button', { name: 'Entrar' }).click();
      await expect(page.getByRole('alert')).toHaveText('Email o contraseña incorrectos');
    }

    // The tenth failure locked the account: even the right password is rejected now.
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Contraseña').fill('lock-test-passphrase');
    await page.getByRole('button', { name: 'Entrar' }).click();
    await expect(page.getByRole('alert')).toHaveText(
      'Cuenta bloqueada temporalmente. Inténtalo en 15 minutos',
    );
  });
});
