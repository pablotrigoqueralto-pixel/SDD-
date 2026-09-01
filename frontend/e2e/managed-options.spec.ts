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

test.describe('options an administrator manages from the form', () => {
  test('adds a specialty mid-form and keeps what was already typed', async ({ page }, testInfo) => {
    const isMobile = testInfo.project.name === 'mobile-chromium';
    const suffix = uniqueSuffix();
    // Distinct provinces and names per project: both runs share the database.
    const province = isMobile ? '30' : '18';
    const centre = `Centro Opciones ${suffix}`;
    const specialty = `Urología ${suffix}`;

    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.goto('/centros/nuevo');
    const accountForm = page.getByRole('dialog');
    await accountForm.getByLabel('Nombre').fill(centre);
    await accountForm.getByRole('combobox', { name: 'Tipo' }).selectOption({ index: 1 });
    await accountForm.getByRole('combobox', { name: 'Provincia' }).selectOption(province);
    await accountForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByRole('heading', { name: centre })).toBeVisible();

    await page.getByRole('button', { name: 'Nuevo contacto' }).first().click();
    const contactForm = page.getByRole('dialog');
    await contactForm.getByLabel('Nombre').fill('Elena');
    await contactForm.getByLabel('Apellidos').fill(`Opciones ${suffix}`);

    // The specialty is missing: create it without leaving the half-filled form.
    await contactForm.getByRole('button', { name: '+ Añadir' }).nth(1).click();
    const addDialog = page.getByRole('dialog').filter({ hasText: 'Añadir especialidad' });
    // Scan the dialog while it is open: closed, axe would never see it.
    await expectNoSeriousA11yViolations(page);
    await addDialog.getByLabel('Nombre').fill(specialty);
    await addDialog.getByRole('button', { name: 'Guardar' }).click();

    // Selected in the field that opened it, with the rest of the form untouched.
    await expect(contactForm.getByRole('combobox', { name: 'Especialidad' })).toHaveValue(/.+/);
    await expect(
      contactForm.getByRole('combobox', { name: 'Especialidad' }).getByRole('option', {
        name: specialty,
      }),
    ).toBeAttached();
    await expect(contactForm.getByLabel('Apellidos')).toHaveValue(`Opciones ${suffix}`);

    await contactForm.getByRole('button', { name: 'Guardar' }).click();
    const contacts = page
      .getByRole('region', { name: /Contactos/ })
      .locator('visible=true')
      .first();
    await expect(contacts.getByText(`Elena Opciones ${suffix}`)).toBeVisible();
    await expect(contacts.getByText(specialty).first()).toBeVisible();

    // The new specialty is a catalogue entry now: it reaches the global contacts list,
    // whose filter controls live in a sheet below lg.
    await page.goto('/contactos');
    if (isMobile) await page.getByRole('button', { name: 'Filtros', exact: true }).click();
    await expect(
      page.getByRole('combobox', { name: 'Especialidad' }).getByRole('option', { name: specialty }),
    ).toBeAttached();

    await expectNoSeriousA11yViolations(page);
  });

  test('a rep never sees the add buttons', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile-chromium', 'One rep per suite is enough.');
    const suffix = uniqueSuffix();
    const repEmail = `rep-options-${suffix}@quermed.com`;
    const repPassword = 'rep-options-passphrase';

    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.goto('/admin/usuarios/nuevo');
    const userForm = page.getByRole('dialog');
    await userForm.getByLabel('Nombre completo').fill(`Rep opciones ${suffix}`);
    await userForm.getByLabel('Email').fill(repEmail);
    await userForm.getByRole('combobox', { name: 'Rol' }).selectOption('sales_rep');
    await userForm.getByLabel('Contraseña').fill(repPassword);
    await userForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(userForm).toBeHidden();

    await logout(page);
    await loginAs(page, repEmail, repPassword);

    await page.goto('/centros/nuevo');
    const form = page.getByRole('dialog');
    await expect(form.getByRole('combobox', { name: 'Tipo' })).toBeVisible();
    await expect(form.getByRole('button', { name: '+ Añadir' })).toHaveCount(0);
  });

  test('reorders advancing stages and never lets a terminal one climb', async ({
    page,
  }, testInfo) => {
    test.skip(
      testInfo.project.name === 'mobile-chromium',
      'Reordering is a desktop administration task and both projects share the pipeline.',
    );

    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.goto('/admin/pipelines');
    const equipment = page.getByRole('region', { name: 'Equipos' });
    const rowNames = async () =>
      (await equipment.getByRole('listitem').allTextContents()).map((text) => text.trim());

    await expect(equipment.getByRole('listitem').first()).toBeVisible();
    const before = await rowNames();
    // Swap the first two rows: this is the interaction that swaps Demo and Presupuesto,
    // without depending on the order the shared database happens to hold.
    const first = before[0]
      .replace(/^\d+/, '')
      .replace(/\d+\s?%.*$/, '')
      .trim();

    await equipment.getByRole('button', { name: `Bajar ${first}` }).click();
    await expect(async () => {
      expect((await rowNames())[1]).toContain(first);
    }).toPass();

    // The terminal stages never move above an advancing one: the guard is unreachable.
    await expect(equipment.getByRole('button', { name: 'Subir Ganada' })).toBeDisabled();
    await expect(equipment.getByRole('button', { name: 'Bajar Perdida' })).toBeDisabled();

    // Leave the pipeline as it was found.
    await equipment.getByRole('button', { name: `Subir ${first}` }).click();
    await expect(async () => {
      expect(await rowNames()).toEqual(before);
    }).toPass();

    await expectNoSeriousA11yViolations(page);
  });
});
