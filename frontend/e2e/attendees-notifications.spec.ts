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

test.describe('attendees and notifications', () => {
  test('a colleague is invited, sees it as a guest and both are told', async ({
    page,
    api,
  }, testInfo) => {
    test.skip(
      testInfo.project.name === 'mobile-chromium',
      'Three logins in one test; the desktop project covers the flow.',
    );
    const suffix = uniqueSuffix();
    const password = 'attendee-e2e-passphrase';
    const ownerEmail = `owner-${suffix}@quermed.com`;
    const guestEmail = `guest-${suffix}@quermed.com`;
    const centre = `Centro Acompañantes ${suffix}`;

    // Two reps of one territory, so both can see the centre: an attendee outside its
    // scope is refused, which is the guard rather than a bug.
    const pool = Array.from({ length: 52 }, (_, i) => String(i + 1).padStart(2, '0'));
    const free = await api.freeProvinces(pool);
    const province = free[Math.floor(free.length / 6)] ?? '';
    expect(province, 'a free province is needed').toBeTruthy();
    const territory = await api.createTerritory(`Acompañantes ${suffix}`, [province]);
    const divisions = await api.listDivisions();
    const scope = {
      territory_ids: [territory.id],
      division_ids: divisions.map((division) => division.id),
    };
    await api.createUser({
      email: ownerEmail,
      full_name: `Dueño ${suffix}`,
      role: 'sales_rep',
      password,
      ...scope,
    });
    await api.createUser({
      email: guestEmail,
      full_name: `Invitado ${suffix}`,
      role: 'sales_rep',
      password,
      ...scope,
    });
    const account = await api.createAccount({ name: centre, province_code: province });

    // The manager plans a visit for one rep with the other coming along.
    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.goto(`/centros/${account.id}`);
    await page.getByRole('button', { name: 'Nueva actividad' }).first().click();
    const activityForm = page.getByRole('dialog');
    await activityForm
      .getByRole('group', { name: 'Tipo de actividad' })
      .getByText('Visita', { exact: true })
      .click();
    // Planned for later today, so it lands in both agendas: "Hoy" lists what is planned.
    await activityForm.getByText('Planificada', { exact: true }).click();
    const laterToday = new Date();
    laterToday.setHours(23, 30, 0, 0);
    const localValue = `${laterToday.getFullYear()}-${String(laterToday.getMonth() + 1).padStart(2, '0')}-${String(laterToday.getDate()).padStart(2, '0')}T23:30`;
    await activityForm.getByLabel('Fecha y hora').fill(localValue);
    await activityForm.getByRole('button', { name: /Más datos/ }).click();
    await activityForm
      .getByRole('combobox', { name: 'Comercial' })
      .selectOption({ label: `Dueño ${suffix}` });
    await activityForm
      .getByRole('group', { name: 'Acompañantes' })
      .getByRole('checkbox', { name: `Invitado ${suffix}` })
      .check({ force: true });
    await activityForm.getByRole('button', { name: 'Guardar' }).click();
    await expect(activityForm).toBeHidden();

    // The guest finds it in their own day, marked as an invitation and read-only.
    await logout(page);
    await loginAs(page, guestEmail, password);
    const notices = page.getByRole('list', { name: 'Novedades' });
    await expect(
      notices.getByText(new RegExp(`añadido a una actividad en ${centre}`)),
    ).toBeVisible();
    await expect(page.getByText('Invitado', { exact: true }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Hecha' })).toHaveCount(0);

    await expectNoSeriousA11yViolations(page);

    // Reading clears the block and the header count.
    await page.getByRole('button', { name: 'Marcar todo como leído' }).click();
    await expect(notices).toBeHidden();
    await expect(page.getByRole('button', { name: /Notificaciones: nada nuevo/ })).toBeVisible();

    // The owner sees the same visit as their own work, with its actions.
    await logout(page);
    await loginAs(page, ownerEmail, password);
    await expect(page.getByRole('button', { name: 'Hecha' }).first()).toBeVisible();
    await expect(page.getByText('Invitado', { exact: true })).toHaveCount(0);
  });

  test('the Listado view lists a range and refuses a year', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile-chromium', 'One run of the range view is enough.');

    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.goto('/hoy');
    await page.getByText('Listado', { exact: true }).click();

    await expect(page.getByLabel('Desde')).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Comercial' })).toBeVisible();

    await page.getByLabel('Desde').fill('2026-01-01');
    await page.getByLabel('Hasta').fill('2026-12-31');

    await expect(page.getByRole('alert')).toHaveText(/92 días/);

    await expectNoSeriousA11yViolations(page);
  });
});
