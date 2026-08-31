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

test.describe('activity calendar', () => {
  test('staff sees the team month with the rep filter; the rep sees only their own', async ({
    page,
    api,
  }, testInfo) => {
    const isMobile = testInfo.project.name === 'mobile-chromium';
    const suffix = uniqueSuffix();
    const password = 'cal-e2e-passphrase';
    const parity = isMobile ? 0 : 1;
    const pool = Array.from({ length: 52 }, (_, i) => String(i + 1).padStart(2, '0')).filter(
      (code) => Number(code) % 2 === parity,
    );
    const provinces = await api.freeProvinces(pool);
    // Index /8 keeps clear of the other specs' picks (first two, last, /2, /3, /4, /5).
    let province = provinces[Math.floor(provinces.length / 8)] ?? '';
    let territoryId: string;
    if (province) {
      territoryId = (await api.createTerritory(`Cal ${suffix}`, [province])).id;
    } else {
      const territories = await api.listTerritories();
      const reusable = territories.find((t) => t.provinces.length > 0);
      expect(reusable, 'an existing territory is needed').toBeTruthy();
      territoryId = reusable!.id;
      province = reusable!.provinces[0]!;
    }
    const divisions = await api.listDivisions();
    const vascular = divisions.find((d) => d.code === 'vascular')!;
    const rep = await api.createUser({
      email: `cal-rep-${suffix}@quermed.com`,
      full_name: `Rep Cal ${suffix}`,
      role: 'sales_rep',
      password,
      territory_ids: [territoryId],
      division_ids: [vascular.id],
    });

    // One planned visit on a quiet day of the current month (never today, so the
    // count stays deterministic while other specs record done-now activities).
    const now = new Date();
    const quietDay = now.getDate() === 25 ? 26 : 25;
    const year = now.getFullYear();
    const month = now.getMonth() + 1;
    const scheduled = `${String(year)}-${String(month).padStart(2, '0')}-${String(quietDay).padStart(2, '0')}T10:00:00Z`;
    const account = await api.createAccount({
      name: `Centro Cal ${suffix}`,
      province_code: province,
    });
    await api.planActivity(account.id, rep.id, scheduled);

    // Exact counts only under an owner scope: the shared team view accumulates
    // activities from the concurrent desktop/mobile runs of this suite.
    const dayCellAnyCount = new RegExp(`^${String(quietDay)} de `);
    const dayCellExactlyOne = new RegExp(`^${String(quietDay)} de .*1 actividad$`);

    // --- Staff: team month, expansion, rep filter, axe ---
    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.getByText('Mes', { exact: true }).click();
    await expect(page.getByRole('grid')).toBeVisible();
    await expect(page.getByRole('button', { name: dayCellAnyCount })).toBeVisible();

    await page.getByRole('button', { name: dayCellAnyCount }).click();
    const dayList = page.getByRole('region', { name: new RegExp(`^${String(quietDay)} de`) });
    await expect(dayList.getByText('Visita', { exact: true }).first()).toBeVisible();
    await expect(dayList.getByText(new RegExp(`Rep Cal ${suffix}`))).toBeVisible();

    await page
      .getByRole('combobox', { name: 'Comercial' })
      .selectOption({ label: `Rep Cal ${suffix}` });
    await expect(page.getByRole('button', { name: dayCellExactlyOne })).toBeVisible();

    await expectNoSeriousA11yViolations(page);
    await logout(page);

    // --- Rep: own month only, no selector ---
    await loginAs(page, rep.email, password);
    await page.getByText('Mes', { exact: true }).click();
    await expect(page.getByRole('grid')).toBeVisible();
    await expect(page.getByRole('button', { name: dayCellExactlyOne })).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Comercial' })).toHaveCount(0);
  });
});
