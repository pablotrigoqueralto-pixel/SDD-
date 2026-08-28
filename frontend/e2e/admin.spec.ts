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

test.describe('administration', () => {
  test('admin creates a territory and a sales rep who then sees only their own screens', async ({
    page,
  }, testInfo) => {
    const suffix = uniqueSuffix();
    const territoryName = `E2E ${suffix}`;
    const repEmail = `rep-${suffix}@quermed.com`;
    const repPassword = 'rep-e2e-passphrase';

    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);

    // Admin hub → territories
    await page.getByRole('link', { name: 'Administración' }).first().click();
    await expect(page.getByRole('heading', { name: 'Administración' })).toBeVisible();
    await expectNoSeriousA11yViolations(page);
    await page.getByRole('link', { name: /Territorios/ }).click();
    await page.getByRole('button', { name: 'Nuevo territorio' }).first().click();
    const territoryForm = page.getByRole('dialog');
    await territoryForm.getByLabel('Nombre').fill(territoryName);
    // Pick a free province (taken ones are disabled); each project takes a different one so the
    // desktop and mobile runs never race for the same province. Fresh DB per CI run.
    const freeProvince = territoryForm
      .getByRole('checkbox', { disabled: false })
      .nth(testInfo.project.name === 'mobile-chromium' ? 1 : 0);
    await freeProvince.check();
    await expect(freeProvince).toBeChecked();
    await territoryForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(territoryForm).toBeHidden();
    await expect(page.getByText(territoryName)).toBeVisible();

    // Users → new sales rep
    await page.goto('/admin/usuarios');
    await page.getByRole('button', { name: 'Nuevo usuario' }).first().click();
    const userForm = page.getByRole('dialog');
    await userForm.getByLabel('Nombre completo').fill(`Rep ${suffix}`);
    await userForm.getByLabel('Email').fill(repEmail);
    await userForm.getByRole('combobox', { name: 'Rol' }).selectOption('sales_rep');
    await userForm.getByRole('checkbox', { name: territoryName }).check();
    await userForm.getByRole('checkbox', { name: 'Vascular' }).check();
    await userForm.getByLabel('Contraseña').fill(repPassword);
    await expect(userForm.getByRole('note')).toHaveCount(0);
    await userForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(userForm).toBeHidden();
    // The list is paginated: search so the new user is on screen whatever the database holds.
    await page.getByRole('searchbox', { name: 'Buscar' }).fill(`Rep ${suffix}`);
    await expect(page.getByText(`Rep ${suffix}`)).toBeVisible();
    await expectNoSeriousA11yViolations(page);

    await logout(page);

    // The rep can log in, has no admin entry and gets "Sin permiso" on admin routes
    await loginAs(page, repEmail, repPassword);
    await expect(page.getByRole('link', { name: 'Administración' })).toHaveCount(0);
    await page.goto('/admin/usuarios');
    await expect(page.getByRole('heading', { name: 'Sin permiso' })).toBeVisible();
    await expectNoSeriousA11yViolations(page);
  });

  test('duplicate email is reported under the field', async ({ page }) => {
    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.goto('/admin/usuarios/nuevo');
    const userForm = page.getByRole('dialog');
    await userForm.getByLabel('Nombre completo').fill('Duplicado');
    await userForm.getByLabel('Email').fill(ADMIN_EMAIL);
    await userForm.getByLabel('Contraseña').fill('another-passphrase-123');
    await userForm.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.getByText('Ya existe un usuario con este email')).toBeVisible();
  });
});
