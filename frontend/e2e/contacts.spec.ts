import { ADMIN_EMAIL, ADMIN_PASSWORD, expect, loginAs, test, uniqueSuffix } from './fixtures/app';
import { expectNoSeriousA11yViolations } from './fixtures/axe';

/** Two centres, each with a contact of a different specialty, then cumulative filtering. */
test.describe('global contacts list with cumulative filters', () => {
  test('filters by specialty, adds a second, narrows by centre and survives a reload', async ({
    page,
  }, testInfo) => {
    const isMobile = testInfo.project.name === 'mobile-chromium';
    const suffix = uniqueSuffix();
    // Distinct provinces per project: both runs share the database.
    const province = isMobile ? '46' : '41';
    const gynaeCentre = `Clínica Especialidades ${suffix}`;
    const vascularCentre = `Hospital Especialidades ${suffix}`;

    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);

    const createCentre = async (name: string) => {
      await page.goto('/centros/nuevo');
      const form = page.getByRole('dialog');
      await form.getByLabel('Nombre').fill(name);
      await form.getByRole('combobox', { name: 'Tipo' }).selectOption({ index: 1 });
      await form.getByRole('combobox', { name: 'Provincia' }).selectOption(province);
      await form.getByRole('button', { name: 'Guardar' }).click();
      await expect(page.getByRole('heading', { name })).toBeVisible();
    };

    const addContact = async (lastName: string, specialty: string) => {
      await page.getByRole('button', { name: 'Nuevo contacto' }).first().click();
      const form = page.getByRole('dialog');
      await form.getByLabel('Nombre').fill('Elena');
      await form.getByLabel('Apellidos').fill(lastName);
      await form.getByRole('combobox', { name: 'Especialidad' }).selectOption({ label: specialty });
      await form.getByRole('button', { name: 'Guardar' }).click();
      // Both layouts render the sections; assert on the visible one.
      await expect(
        page.getByText(`Elena ${lastName}`).locator('visible=true').first(),
      ).toBeVisible();
    };

    await createCentre(gynaeCentre);
    await addContact(`Ginecología ${suffix}`, 'Ginecología');
    // The centre's derived specialties appear on its 360º.
    await expect(
      page
        .getByRole('list', { name: 'Especialidades' })
        .locator('visible=true')
        .first()
        .getByText('Ginecología'),
    ).toBeVisible();

    await createCentre(vascularCentre);
    await addContact(`Vascular ${suffix}`, 'Cirugía Vascular');

    await page.goto('/contactos');
    const list = page
      .getByRole('list', { name: 'Contactos' })
      .or(page.getByRole('table', { name: 'Contactos' }));
    await page.getByRole('searchbox', { name: 'Buscar por nombre' }).fill(suffix);
    await expect(list.getByText(`Elena Ginecología ${suffix}`)).toBeVisible();
    await expect(list.getByText(`Elena Vascular ${suffix}`)).toBeVisible();

    // Below lg: the controls live in a sheet, so open it before every pick and apply after.
    const pickFilter = async (name: string, option: string) => {
      // exact: "Filtros" would also match the "Quitar filtros" action.
      if (isMobile) await page.getByRole('button', { name: 'Filtros', exact: true }).click();
      await page.getByRole('combobox', { name }).selectOption({ label: option });
      if (isMobile) await page.getByRole('button', { name: 'Aplicar' }).click();
    };

    // One specialty narrows the list. The list keeps the previous rows on screen while the
    // filtered request is in flight, so wait for the chip (the URL is already updated) and
    // give the request room: the whole suite hammers the same backend.
    await pickFilter('Especialidad', 'Ginecología');
    await expect(page.getByRole('list', { name: 'Filtros' }).getByRole('listitem')).toHaveCount(1);
    await expect(list.getByText(`Elena Vascular ${suffix}`)).toBeHidden({ timeout: 15_000 });

    // A second specialty ADDS UP: both contacts come back, with two chips.
    await pickFilter('Especialidad', 'Cirugía Vascular');
    const chips = page.getByRole('list', { name: 'Filtros' });
    await expect(chips.getByRole('listitem')).toHaveCount(2);
    await expect(list.getByText(`Elena Vascular ${suffix}`)).toBeVisible();
    await expect(list.getByText(`Elena Ginecología ${suffix}`)).toBeVisible();

    // A different filter NARROWS: only that centre's contact remains.
    await pickFilter('Centro', vascularCentre);
    await expect(chips.getByRole('listitem')).toHaveCount(3);
    await expect(list.getByText(`Elena Ginecología ${suffix}`)).toBeHidden({ timeout: 15_000 });
    await expect(list.getByText(`Elena Vascular ${suffix}`)).toBeVisible();

    // The URL carries the state: reloading reproduces exactly this list.
    const filteredUrl = page.url();
    expect(filteredUrl).toContain('specialty_id=');
    await page.reload();
    await expect(page.getByRole('list', { name: 'Filtros' }).getByRole('listitem')).toHaveCount(3);
    await expect(list.getByText(`Elena Vascular ${suffix}`)).toBeVisible();

    // Removing one chip keeps the rest.
    await page.getByRole('button', { name: 'Quitar filtro Ginecología' }).click();
    await expect(page.getByRole('list', { name: 'Filtros' }).getByRole('listitem')).toHaveCount(2);
    await expect(list.getByText(`Elena Vascular ${suffix}`)).toBeVisible();

    await expectNoSeriousA11yViolations(page);
  });
});
