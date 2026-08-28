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

test.describe('reference data administration', () => {
  test('admin manages brands, loss reasons and pipeline stages; reps cannot', async ({
    page,
    api,
  }) => {
    const suffix = uniqueSuffix();
    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);

    // Brands: create a competitor and rename it
    await page.goto('/admin/marcas');
    await expectNoSeriousA11yViolations(page);
    await page.getByRole('button', { name: 'Nueva marca' }).first().click();
    const brandForm = page.getByRole('dialog');
    await brandForm.getByLabel('Nombre').fill(`Competidor ${suffix}`);
    await brandForm.getByRole('combobox', { name: 'Tipo' }).selectOption('competitor');
    await brandForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(brandForm).toBeHidden();
    await expect(page.getByText(`Competidor ${suffix}`)).toBeVisible();

    // Cards on mobile, table rows on desktop: the text is the stable handle for both.
    await page.getByText(`Competidor ${suffix}`, { exact: true }).click();
    const editForm = page.getByRole('dialog');
    await editForm.getByLabel('Nombre').fill(`Competidor ${suffix} SA`);
    await editForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(editForm).toBeHidden();
    await expect(page.getByText(`Competidor ${suffix} SA`)).toBeVisible();

    // Loss reasons: add one
    await page.goto('/admin/motivos-perdida');
    await expectNoSeriousA11yViolations(page);
    await page.getByRole('button', { name: 'Nuevo motivo' }).first().click();
    const reasonForm = page.getByRole('dialog');
    await reasonForm.getByLabel('Nombre').fill(`Motivo ${suffix}`);
    await reasonForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(reasonForm).toBeHidden();
    await expect(page.getByText(`Motivo ${suffix}`)).toBeVisible();

    // Pipelines: move the first consumables stage down and back, then tune a probability
    await page.goto('/admin/pipelines');
    await expectNoSeriousA11yViolations(page);
    const consumables = page.getByRole('region', { name: 'Consumibles' });
    const firstRow = consumables.getByRole('listitem').first();
    const firstName = (await firstRow.locator('span.flex-1').textContent()) ?? '';
    await firstRow.getByRole('button', { name: `Bajar ${firstName}` }).click();
    await expect(consumables.getByRole('listitem').nth(1)).toContainText(firstName);
    await consumables.getByRole('button', { name: `Subir ${firstName}` }).click();
    await expect(consumables.getByRole('listitem').first()).toContainText(firstName);

    const editButton = consumables.getByRole('button', { name: `Editar ${firstName}` });
    await editButton.click();
    const stageForm = page.getByRole('dialog');
    const probabilityInput = stageForm.getByLabel('Probabilidad (%)');
    const original = await probabilityInput.inputValue();
    await probabilityInput.fill('21');
    await stageForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(stageForm).toBeHidden();
    await expect(consumables.getByRole('listitem').first()).toContainText('21 %');
    // Restore the seeded value so repeated runs start from the same state.
    await editButton.click();
    await page.getByRole('dialog').getByLabel('Probabilidad (%)').fill(original);
    await page.getByRole('dialog').getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByRole('dialog')).toBeHidden();

    // A sales rep gets "Sin permiso"
    const repEmail = `rep-ref-${suffix}@quermed.com`;
    await api.createUser({
      email: repEmail,
      full_name: `Rep ${suffix}`,
      role: 'sales_rep',
      password: 'rep-e2e-passphrase',
    });
    await logout(page);
    await loginAs(page, repEmail, 'rep-e2e-passphrase');
    await page.goto('/admin/marcas');
    await expect(page.getByRole('heading', { name: 'Sin permiso' })).toBeVisible();
  });
});
