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

test.describe('accounts and contacts', () => {
  test('rep creates a centre and a contact; manager reassigns; other rep is denied', async ({
    page,
    api,
  }, testInfo) => {
    const suffix = uniqueSuffix();
    const repPassword = 'rep-e2e-passphrase';
    // Each project owns different provinces so the desktop and mobile runs never race.
    // Odd codes for desktop, even for mobile: the two projects never compete for a province.
    const parity = testInfo.project.name === 'mobile-chromium' ? 0 : 1;
    const pool = Array.from({ length: 52 }, (_, i) => String(i + 1).padStart(2, '0')).filter(
      (code) => Number(code) % 2 === parity,
    );
    const [ownProvince, otherProvince] = await api.freeProvinces(pool);
    expect(ownProvince && otherProvince, 'two free provinces are needed').toBeTruthy();
    const territory = await api.createTerritory(`T ${suffix}`, [ownProvince]);
    const otherTerritory = await api.createTerritory(`O ${suffix}`, [otherProvince]);
    const divisions = await api.listDivisions();
    const vascular = divisions.find((d) => d.code === 'vascular')!;
    const rep = await api.createUser({
      email: `rep-${suffix}@quermed.com`,
      full_name: `Rep ${suffix}`,
      role: 'sales_rep',
      password: repPassword,
      territory_ids: [territory.id],
      division_ids: [vascular.id],
    });
    const otherRep = await api.createUser({
      email: `other-${suffix}@quermed.com`,
      full_name: `Other ${suffix}`,
      role: 'sales_rep',
      password: repPassword,
      territory_ids: [otherTerritory.id],
      division_ids: [vascular.id],
    });
    const manager = await api.createUser({
      email: `manager-${suffix}@quermed.com`,
      full_name: `Manager ${suffix}`,
      role: 'sales_manager',
      password: repPassword,
    });
    const accountName = `Clínica ${suffix}`;

    // Rep: three fields → 360º page
    await loginAs(page, rep.email, repPassword);
    await page.getByRole('link', { name: 'Centros' }).first().click();
    await expect(page.getByRole('heading', { name: 'Centros' })).toBeVisible();
    await expectNoSeriousA11yViolations(page);
    await page.getByRole('button', { name: 'Nuevo centro' }).first().click();
    const form = page.getByRole('dialog');
    await form.getByLabel('Nombre').fill(accountName);
    await form.getByRole('combobox', { name: 'Tipo' }).selectOption({ index: 1 });
    await form.getByRole('combobox', { name: 'Provincia' }).selectOption(ownProvince);
    await expect(form.getByRole('note')).toContainText('Comercial: tú');
    await form.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByRole('heading', { name: accountName })).toBeVisible();
    await expect(page.getByText(`Comercial: Rep ${suffix}`)).toBeVisible();
    await expectNoSeriousA11yViolations(page);
    const accountUrl = page.url();

    // Contact with consent
    await page.getByRole('button', { name: 'Nuevo contacto' }).first().click();
    const contactForm = page.getByRole('dialog');
    await contactForm.getByLabel('Nombre').fill('Ana');
    await contactForm.getByLabel('Apellidos').fill(`Pérez ${suffix}`);
    await contactForm.getByRole('textbox', { name: 'Móvil' }).fill('612345678');
    await contactForm.getByRole('radio', { name: 'Móvil' }).check();
    await contactForm.getByRole('combobox', { name: 'Estado' }).selectOption('granted');
    await contactForm.getByRole('combobox', { name: 'Origen' }).selectOption('verbal');
    await contactForm.getByLabel('Contacto principal').check();
    await contactForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(contactForm).toBeHidden();
    // The 360º page renders a mobile and a desktop layout; assert on the visible copy.
    const card = page
      .getByRole('article')
      .filter({ hasText: `Ana Pérez ${suffix}` })
      .locator('visible=true')
      .first();
    await expect(card.getByText('Principal')).toBeVisible();
    await expect(card.getByText('Concedido')).toBeVisible();
    await expect(card.getByRole('link', { name: /Llamar a Ana/ })).toHaveAttribute(
      'href',
      'tel:+34612345678',
    );

    // Edit the contact
    await card.getByRole('button', { name: 'Editar' }).click();
    const editForm = page.getByRole('dialog');
    await editForm.getByLabel('Nombre').fill('Ana María');
    await editForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(editForm).toBeHidden();
    await expect(
      page.getByText(`Ana María Pérez ${suffix}`).locator('visible=true').first(),
    ).toBeVisible();
    await logout(page);

    // Other rep: direct URL → not found
    await loginAs(page, otherRep.email, repPassword);
    await page.goto(accountUrl);
    await expect(page.getByRole('heading', { name: 'Centro no encontrado' })).toBeVisible();
    await expectNoSeriousA11yViolations(page);
    await logout(page);

    // Manager reassigns to the other rep
    await loginAs(page, manager.email, repPassword);
    await page.goto(accountUrl);
    await page.getByRole('button', { name: 'Reasignar' }).click();
    const assignForm = page.getByRole('dialog');
    await assignForm.getByRole('combobox', { name: 'Comercial' }).selectOption(otherRep.id);
    // A focused native <select> keeps its popup over the button on mobile Chromium: submit by key.
    await assignForm.getByRole('button', { name: 'Guardar' }).press('Enter');
    await expect(assignForm).toBeHidden();
    await expect(page.getByText(`Comercial: Other ${suffix}`)).toBeVisible();
    await logout(page);

    // The other rep now owns it
    await loginAs(page, otherRep.email, repPassword);
    await page.goto(accountUrl);
    await expect(page.getByRole('heading', { name: accountName })).toBeVisible();
  });

  test('admin adds a job title that appears in the contact form', async ({ page }) => {
    const suffix = uniqueSuffix();
    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.goto('/admin/cargos');
    await expectNoSeriousA11yViolations(page);
    await page.getByRole('button', { name: 'Nuevo cargo' }).first().click();
    const form = page.getByRole('dialog');
    await form.getByLabel('Nombre').fill(`Cargo ${suffix}`);
    await form.getByRole('button', { name: 'Guardar' }).click();
    await expect(form).toBeHidden();
    await expect(page.getByText(`Cargo ${suffix}`)).toBeVisible();
  });
});
