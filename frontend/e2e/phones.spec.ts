import { ADMIN_EMAIL, ADMIN_PASSWORD, expect, loginAs, test, uniqueSuffix } from './fixtures/app';
import { expectNoSeriousA11yViolations } from './fixtures/axe';

test.describe('labelled phones, billing notes and head of department', () => {
  test('a centre keeps several labelled phones and is found by a secondary number', async ({
    page,
  }, testInfo) => {
    const isMobile = testInfo.project.name === 'mobile-chromium';
    const suffix = uniqueSuffix();
    // Distinct numbers per project: both runs share the database.
    const switchboard = isMobile ? '915550020' : '915550010';
    const service = isMobile ? '915550021' : '915550011';
    const accountName = `Hospital Teléfonos ${suffix}`;

    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.goto('/centros/nuevo');

    const form = page.getByRole('dialog');
    await form.getByLabel('Nombre').fill(accountName);
    await form.getByRole('combobox', { name: 'Tipo' }).selectOption({ index: 1 });
    await form.getByRole('combobox', { name: 'Provincia' }).selectOption('28');
    await form.getByRole('button', { name: 'Más datos' }).click();

    await form.getByRole('button', { name: 'Añadir teléfono' }).click();
    await form.getByRole('combobox', { name: 'Etiqueta' }).fill('Centralita');
    await form.getByRole('textbox', { name: 'Número' }).fill(switchboard);

    await form.getByRole('button', { name: 'Añadir teléfono' }).click();
    await form.getByRole('combobox', { name: 'Etiqueta' }).nth(1).fill('Servicio de vascular');
    await form.getByRole('textbox', { name: 'Número' }).nth(1).fill(service);
    await form.getByRole('textbox', { name: 'Extensión' }).nth(1).fill('4021');

    await form
      .getByLabel('Datos de facturación y contacto de contabilidad')
      .fill('Factura por FACe. Contabilidad: Marta Gil.');
    await form.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.getByRole('heading', { name: accountName })).toBeVisible();

    // The 360º shows both labelled numbers as tel: links, with the extension.
    const data = page.getByRole('region', { name: 'Datos' }).locator('visible=true').first();
    await expect(data.getByText('Centralita')).toBeVisible();
    await expect(data.getByRole('link', { name: `+34${switchboard}` })).toHaveAttribute(
      'href',
      `tel:+34${switchboard}`,
    );
    await expect(data.getByRole('link', { name: /ext\. 4021/ })).toHaveAttribute(
      'href',
      `tel:+34${service};ext=4021`,
    );
    // Both layouts render the sections; assert on the visible one.
    await expect(
      page
        .getByText(/Factura por FACe/)
        .locator('visible=true')
        .first(),
    ).toBeVisible();

    await expectNoSeriousA11yViolations(page);

    // A contact with a cargo AND the head-of-department tick.
    await page.getByRole('button', { name: 'Nuevo contacto' }).first().click();
    const contactForm = page.getByRole('dialog');
    await contactForm.getByLabel('Nombre').fill('Miguel');
    await contactForm.getByLabel('Apellidos').fill(`Serrano ${suffix}`);
    await contactForm.getByRole('combobox', { name: 'Cargo' }).selectOption({ index: 1 });
    await contactForm.getByLabel('Jefe/a de servicio').check();
    await contactForm.getByRole('button', { name: 'Guardar' }).click();

    const contacts = page
      .getByRole('region', { name: /Contactos/ })
      .locator('visible=true')
      .first();
    await expect(contacts.getByText(`Miguel Serrano ${suffix}`)).toBeVisible();
    await expect(contacts.getByText('Jefe/a de servicio').first()).toBeVisible();

    // Search by the SECONDARY number finds the centre.
    await page.goto('/buscar');
    await page.getByRole('searchbox', { name: 'Buscar' }).fill(service);
    await expect(page.getByRole('button', { name: new RegExp(accountName) })).toBeVisible();
  });
});
