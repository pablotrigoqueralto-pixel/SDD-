import { expect, loginAs, logout, test, uniqueSuffix } from './fixtures/app';
import { expectNoSeriousA11yViolations } from './fixtures/axe';

test.describe('activities and timeline', () => {
  test('rep records a visit with a next action, closes it from Hoy; manager views the day', async ({
    page,
    api,
  }, testInfo) => {
    const suffix = uniqueSuffix();
    const password = 'rep-e2e-passphrase';
    const parity = testInfo.project.name === 'mobile-chromium' ? 0 : 1;
    const pool = Array.from({ length: 52 }, (_, i) => String(i + 1).padStart(2, '0')).filter(
      (code) => Number(code) % 2 === parity,
    );
    // Take from the end of the pool: accounts.spec takes from the start on the same project.
    const [province] = (await api.freeProvinces(pool)).reverse();
    expect(province, 'a free province is needed').toBeTruthy();
    const territory = await api.createTerritory(`A ${suffix}`, [province]);
    const divisions = await api.listDivisions();
    const vascular = divisions.find((d) => d.code === 'vascular')!;
    const rep = await api.createUser({
      email: `act-rep-${suffix}@quermed.com`,
      full_name: `Rep ${suffix}`,
      role: 'sales_rep',
      password,
      territory_ids: [territory.id],
      division_ids: [vascular.id],
    });
    const manager = await api.createUser({
      email: `act-mgr-${suffix}@quermed.com`,
      full_name: `Manager ${suffix}`,
      role: 'sales_manager',
      password,
    });
    const accountName = `Centro ${suffix}`;

    await loginAs(page, rep.email, password);
    await expectNoSeriousA11yViolations(page);

    // Create the centre through the UI (three fields)
    await page.goto('/centros/nuevo');
    const accountForm = page.getByRole('dialog');
    await accountForm.getByLabel('Nombre').fill(accountName);
    await accountForm.getByRole('combobox', { name: 'Tipo' }).selectOption({ index: 1 });
    await accountForm.getByRole('combobox', { name: 'Provincia' }).selectOption(province);
    await accountForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByRole('heading', { name: accountName })).toBeVisible();
    await expect(page.getByText(/Último contacto: Nunca/).first()).toBeVisible();
    const accountUrl = page.url();

    // Record a visit with a next action (planned call for tomorrow 09:00)
    await page.getByRole('button', { name: 'Nueva actividad' }).first().click();
    const activityForm = page.getByRole('dialog');
    // The radio input is visually hidden (sr-only); its label is the touch target.
    await activityForm
      .locator('label')
      .filter({ hasText: /^Visita$/ })
      .click();
    await activityForm.getByRole('button', { name: 'Más datos (opcional)' }).click();
    await activityForm.getByRole('textbox', { name: 'Asunto' }).first().fill(`Demo ${suffix}`);
    await activityForm.getByRole('combobox', { name: 'Tipo' }).selectOption('Llamada');
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const iso = `${tomorrow.toISOString().slice(0, 10)}T09:00`;
    await activityForm.getByLabel('Cuándo').fill(iso);
    await activityForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(activityForm).toBeHidden();
    await expect(page.getByText(`Demo ${suffix}`).locator('visible=true').first()).toBeVisible();
    await expect(page.getByText(/Último contacto: (?!Nunca)/).first()).toBeVisible();
    await expectNoSeriousA11yViolations(page);

    // The follow-up call is planned: reschedule it to today so it shows in "Hoy", then close it
    const timelineCall = page
      .getByRole('article')
      .filter({ hasText: 'Llamada' })
      .locator('visible=true')
      .first();
    await timelineCall.getByRole('button', { name: 'Reprogramar' }).click();
    const resched = page.getByRole('dialog');
    const today = new Date();
    today.setHours(23, 0, 0, 0);
    const pad = (n: number) => String(n).padStart(2, '0');
    await resched
      .getByLabel('Nueva fecha y hora')
      .fill(
        `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}T${pad(today.getHours())}:00`,
      );
    await resched.getByRole('button', { name: 'Guardar' }).click();
    await expect(resched).toBeHidden();

    await page.goto('/hoy');
    await expectNoSeriousA11yViolations(page);
    const planned = page.getByRole('region', { name: /^Hoy \(/ });
    const card = planned.getByRole('article').filter({ hasText: accountName }).first();
    await expect(card).toBeVisible();
    await card.getByRole('button', { name: 'Hecha' }).click();
    const complete = page.getByRole('dialog');
    await complete.getByRole('combobox', { name: 'Resultado' }).selectOption('positive');
    await complete.getByRole('button', { name: 'Guardar' }).click();
    await expect(complete).toBeHidden();
    await expect(planned.getByRole('article').filter({ hasText: accountName })).toHaveCount(0);

    // Timeline shows both, the list shows the recency column
    await page.goto(`${accountUrl}/actividades`);
    await expect(page.getByRole('heading', { name: `Actividades · ${accountName}` })).toBeVisible();
    await expect(page.getByRole('article')).toHaveCount(2);
    await expect(page.getByText('Positiva').first()).toBeVisible();
    await expectNoSeriousA11yViolations(page);
    await logout(page);

    // Manager views the rep's day (empty now) with the rep selector
    await loginAs(page, manager.email, password);
    await page.goto('/hoy');
    await page.getByRole('combobox', { name: 'Comercial' }).selectOption(rep.id);
    await expect(page.getByText('Nada planificado para hoy')).toBeVisible();
    await expect(page.getByText(/1 visita/)).toBeVisible();
  });
});
