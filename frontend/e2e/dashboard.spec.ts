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

test.describe('dashboards', () => {
  test('admin reads the Informes panel and a manager gets the Hoy key figures', async ({
    page,
    api,
  }, testInfo) => {
    const isMobile = testInfo.project.name === 'mobile-chromium';
    const suffix = uniqueSuffix();
    const password = 'dash-e2e-passphrase';
    const parity = isMobile ? 0 : 1;
    const pool = Array.from({ length: 52 }, (_, i) => String(i + 1).padStart(2, '0')).filter(
      (code) => Number(code) % 2 === parity,
    );
    // Reuse an existing territory when the local DB has claimed every province.
    const provinces = await api.freeProvinces(pool);
    // Index /5 keeps clear of the other specs' picks (/2, /3, /4, first two, last).
    let province = provinces[Math.floor(provinces.length / 5)] ?? '';
    let territoryId: string;
    if (province) {
      territoryId = (await api.createTerritory(`Dash ${suffix}`, [province])).id;
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
      email: `dash-rep-${suffix}@quermed.com`,
      full_name: `Rep Dash ${suffix}`,
      role: 'sales_rep',
      password,
      territory_ids: [territoryId],
      division_ids: [vascular.id],
    });
    const manager = await api.createUser({
      email: `dash-mgr-${suffix}@quermed.com`,
      full_name: `Mgr Dash ${suffix}`,
      role: 'sales_manager',
      password,
    });

    // A won deal, an open deal closing today (forecast + pipeline) and a done visit.
    const account = await api.createAccount({
      name: `Centro Dash ${suffix}`,
      province_code: province,
    });
    const wonAmount = isMobile ? '23459.00' : '23457.00';
    const won = await api.createOpportunity({
      account_id: account.id,
      division_id: vascular.id,
      estimated_amount: wonAmount,
      owner_id: rep.id,
      name: `Dash won ${suffix}`,
    });
    await api.winOpportunity(won.id, won.version, wonAmount);
    await api.createOpportunity({
      account_id: account.id,
      division_id: vascular.id,
      estimated_amount: '10000.00',
      owner_id: rep.id,
      name: `Dash open ${suffix}`,
      expected_close_date: new Date().toISOString().slice(0, 10),
    });
    await api.recordDoneActivity(account.id, rep.id);

    const wonPattern = isMobile ? /23\.459,00/ : /23\.457,00/;

    // --- Admin: Más → Informes, KPI figures, breakdowns, period switch, axe ---
    await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.goto('/mas');
    await page.getByRole('link', { name: /Informes/ }).click();
    await expect(page.getByRole('heading', { name: 'Informes', level: 1 })).toBeVisible();

    await expect(page.getByText(wonPattern).first()).toBeVisible();
    await expect(page.getByText('Importe × probabilidad de etapa')).toBeVisible();
    await expect(page.getByRole('region', { name: 'Pipeline por etapa' })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Por división' })).toBeVisible();
    const reps = page.getByRole('region', { name: 'Por comercial' });
    await expect(reps.getByText(`Rep Dash ${suffix}`)).toBeVisible();
    const activity = page.getByRole('region', { name: 'Actividad' });
    const activityRow = activity
      .getByRole('listitem')
      .filter({ hasText: `Rep Dash ${suffix}` });
    await expect(activityRow).toBeVisible();
    await expect(activityRow).toContainText('Visita 1');
    await expect(page.getByRole('region', { name: 'Centros descuidados' })).toBeVisible();

    await page.getByText('Trimestre', { exact: true }).click();
    await expect(page.getByText(wonPattern).first()).toBeVisible();

    await expectNoSeriousA11yViolations(page);

    await logout(page);

    // --- Manager: the Hoy key-figures block links to Informes ---
    await loginAs(page, manager.email, password);
    // The teaser shows company totals (the persistent DB accumulates other runs' wins),
    // so assert the three labelled figures rather than an exact amount.
    const teaser = page.getByRole('link', { name: 'Cifras del mes' });
    await expect(teaser).toBeVisible();
    await expect(teaser).toContainText('Ganado');
    await expect(teaser).toContainText('Previsión');
    await expect(teaser).toContainText('Pipeline abierto');
    await expect(teaser).toContainText('€');
    await teaser.click();
    await expect(page.getByRole('heading', { name: 'Informes', level: 1 })).toBeVisible();
  });
});
