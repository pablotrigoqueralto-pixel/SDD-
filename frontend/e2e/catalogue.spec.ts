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

test.describe('product catalogue', () => {
  test('admin creates a family, back office a product; rep sees no cost, manager does', async ({
    page,
    api,
  }) => {
    const suffix = uniqueSuffix();
    const password = 'cat-e2e-passphrase';
    const familyName = `Láser ${suffix}`;
    const sku = `E2E-${suffix.toUpperCase()}`;
    const productName = `Láser vascular ${suffix}`;
    const divisions = await api.listDivisions();
    const vascular = divisions.find((d) => d.code === 'vascular')!;
    const backOffice = await api.createUser({
      email: `cat-bo-${suffix}@quermed.com`,
      full_name: `Back office ${suffix}`,
      role: 'back_office',
      password,
    });
    const rep = await api.createUser({
      email: `cat-rep-${suffix}@quermed.com`,
      full_name: `Rep ${suffix}`,
      role: 'sales_rep',
      password,
      division_ids: [vascular.id],
    });
    const manager = await api.createUser({
      email: `cat-mgr-${suffix}@quermed.com`,
      full_name: `Manager ${suffix}`,
      role: 'sales_manager',
      password,
    });

    // Admin creates the family through the UI
    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.goto('/admin/familias');
    await expect(page.getByRole('heading', { name: 'Familias de producto' })).toBeVisible();
    await expectNoSeriousA11yViolations(page);
    await page.getByRole('button', { name: 'Nueva familia' }).first().click();
    const familyForm = page.getByRole('dialog');
    await familyForm.getByLabel('Nombre').fill(familyName);
    await familyForm.getByRole('combobox', { name: 'División' }).selectOption(vascular.id);
    await familyForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByText(familyName).first()).toBeVisible();
    await logout(page);

    // Back office creates the product with a cost
    await loginAs(page, backOffice.email, password);
    await page.goto('/mas');
    await page.getByRole('link', { name: /Catálogo/ }).click();
    await expect(page.getByRole('heading', { name: 'Catálogo', level: 1 })).toBeVisible();
    await expectNoSeriousA11yViolations(page);
    await page.getByRole('button', { name: 'Nuevo producto' }).first().click();
    const productForm = page.getByRole('dialog');
    await productForm.getByLabel('Código Sage').fill(sku.toLowerCase());
    await productForm.getByLabel('Nombre').fill(productName);
    await productForm.getByRole('combobox', { name: 'Marca' }).selectOption({ label: 'Hadeco' });
    await productForm
      .getByRole('combobox', { name: 'Familia' })
      .selectOption({ label: familyName });
    // The radio input is visually hidden (sr-only); its label is the touch target.
    await productForm
      .locator('label')
      .filter({ hasText: /^Equipo$/ })
      .click();
    await productForm.getByLabel('Precio de lista').fill('12.500,50');
    await expect(productForm.getByLabel('Coste')).toHaveCount(0);
    await expectNoSeriousA11yViolations(page);
    await productForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await page.getByRole('searchbox', { name: 'Buscar' }).fill(sku);
    await expect(page.getByText(productName).first()).toBeVisible();
    await expect(page.getByText(sku).first()).toBeVisible();
    await logout(page);

    // Rep searches by code prefix: no cost, no create action, read-only form
    await loginAs(page, rep.email, password);
    await page.goto(`/catalogo?q=${encodeURIComponent(sku)}`);
    await expect(page.getByText(productName).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Nuevo producto' })).toHaveCount(0);
    await page.getByText(productName).first().click();
    const readOnly = page.getByRole('dialog');
    await expect(readOnly.getByLabel('Nombre')).toBeDisabled();
    await expect(readOnly.getByLabel('Coste')).toHaveCount(0);
    await expect(readOnly.getByRole('button', { name: 'Guardar' })).toHaveCount(0);
    await logout(page);

    // Manager sees the cost (empty: back office left it blank) and can retire the product
    await loginAs(page, manager.email, password);
    await page.goto(`/catalogo?q=${encodeURIComponent(sku)}`);
    await page.getByText(productName).first().click();
    const managerView = page.getByRole('dialog');
    await expect(managerView.getByLabel('Coste')).toBeVisible();
    await expect(managerView.getByLabel('Coste')).toBeDisabled();
    await logout(page);

    // Admin retires it: it disappears from the rep's default list
    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.goto(`/catalogo?q=${encodeURIComponent(sku)}`);
    await page.getByText(productName).first().click();
    const adminForm = page.getByRole('dialog');
    await adminForm.getByLabel('Activo').uncheck();
    await adminForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await logout(page);

    await loginAs(page, rep.email, password);
    await page.goto(`/catalogo?q=${encodeURIComponent(sku)}`);
    await expect(page.getByText('No hay productos que coincidan')).toBeVisible();
  });
});
